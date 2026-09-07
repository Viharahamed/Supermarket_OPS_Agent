# tests/test_postgres_compatibility.py
"""PostgreSQL Compatibility & Integration Test Suite (Phase 13A.3).

Verifies dialect-aware engine creation, connection pooling parameters,
and full database workflow execution against PostgreSQL connection strings.
"""

import os
from decimal import Decimal
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.database import _configure_engine, Base, init_db, get_db_context
from app.db.models import Product, Customer, Bill, StockMovement, KhataTransaction
from app.services.inventory_service import create_product, receive_stock, get_stock
from app.services.billing_service import create_draft_bill, add_bill_item, finalize_bill
from app.services.payment_service import process_payment


def _require_psycopg():
    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg PostgreSQL driver is not installed in the environment.")


@pytest.mark.postgres
def test_postgres_engine_configuration():
    """Verify that PostgreSQL engine creation configures pool options correctly without SQLite parameters."""
    _require_psycopg()
    postgres_url = "postgresql+psycopg://test_user:test_pass@localhost:5432/kirana_test"
    with patch.dict(os.environ, {
        "DATABASE_URL": postgres_url,
        "DB_POOL_SIZE": "10",
        "DB_MAX_OVERFLOW": "15",
        "DB_POOL_TIMEOUT": "45",
        "DB_POOL_RECYCLE": "900",
        "DB_POOL_PRE_PING": "true",
    }):
        settings = Settings(_env_file=None)
        engine = _configure_engine(settings)

        assert engine.url.render_as_string(hide_password=False) == postgres_url
        assert engine.pool.size() == 10
        assert engine.pool._max_overflow == 15
        assert engine.pool._timeout == 45
        assert engine.pool._recycle == 900
        assert engine.pool._pre_ping is True


@pytest.mark.postgres
def test_postgres_engine_from_url_string():
    """Verify _configure_engine accepts raw string PostgreSQL URL."""
    _require_psycopg()
    postgres_url = "postgresql+psycopg://kirana:secret@localhost:5432/kirana_prod"
    engine = _configure_engine(postgres_url)
    assert engine.url.render_as_string(hide_password=False) == postgres_url


@pytest.mark.postgres
def test_postgres_live_database_workflow():
    """Integration test against a live PostgreSQL database if configured.
    
    Skipped automatically if no live PostgreSQL instance or driver is available.
    """
    _require_psycopg()
    pg_url = os.getenv("POSTGRES_TEST_URL") or os.getenv("DATABASE_URL")
    if not pg_url or not pg_url.startswith("postgresql"):
        pytest.skip("Live PostgreSQL database not configured (POSTGRES_TEST_URL not set).")

    try:
        test_engine = _configure_engine(pg_url)
        # Verify connection capability
        with test_engine.connect() as conn:
            pass
    except Exception as exc:
        pytest.skip(f"Live PostgreSQL server connection failed: {exc}")

    # Build schema on live Postgres database
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with get_db_context(TestSessionLocal) as db:
        # 1. Product creation
        product = create_product(
            db=db,
            name="PG Test Atta",
            sku="PG-ATTA-1KG",
            cost_price="40.00",
            selling_price="50.00",
            mrp="55.00",
            stock_quantity="10.00",
        )
        assert product.id is not None

        # 2. Receive stock
        receive_stock(
            db=db,
            product_id=product.id,
            quantity="20.00",
            cost_price="40.00",
            mrp="55.00",
        )
        stock_status = get_stock(db, product.id)
        assert stock_status.stock_quantity == Decimal("30.00")

        # 3. Create draft bill & finalize
        draft = create_draft_bill(db=db)
        add_bill_item(db=db, bill_id=draft.id, product_id=product.id, quantity="5.00")
        finalized = finalize_bill(db=db, bill_id=draft.id, payment_method="CASH")

        assert finalized.status == "FINALIZED"
        final_stock = get_stock(db, product.id)
        assert final_stock.stock_quantity == Decimal("25.00")

    # Cleanup test tables
    Base.metadata.drop_all(bind=test_engine)

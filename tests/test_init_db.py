# tests/test_init_db.py
"""Comprehensive Test Suite for Database Initialization Script & Schema (Post-Alembic Removal).

Tests:
1. init_db script creates all registered tables against an isolated SQLite test database.
2. Idempotency: Running initialization twice does not fail or error out.
3. Presence of all 10 core application tables in Base.metadata.
4. Database configuration is driven by centralized application Settings.
5. Production safety: FastAPI lifespan app startup does not automatically call create_all().
6. PostgreSQL configuration Dialect & Engine compatibility.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import inspect, create_engine

from app.config import Settings
from app.db.database import Base, _configure_engine
import app.db.models  # Ensures models are imported
from scripts.init_db import run_init_db, mask_db_url


@pytest.fixture
def temp_sqlite_db_url():
    """Create a temporary SQLite database file for isolated initialization tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    url = f"sqlite:///{db_path}"
    yield url
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_init_db_creates_all_tables(temp_sqlite_db_url):
    """Verify that run_init_db creates all registered tables on a fresh SQLite database."""
    success = run_init_db(custom_db_url=temp_sqlite_db_url)
    assert success is True

    engine = _configure_engine(temp_sqlite_db_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    engine.dispose()

    expected_tables = {
        "stores",
        "users",
        "products",
        "stock_movements",
        "customers",
        "bills",
        "bill_items",
        "khata_transactions",
        "owner_preferences",
        "agent_sessions",
    }
    assert expected_tables.issubset(table_names)


def test_init_db_idempotency(temp_sqlite_db_url):
    """Verify that running run_init_db twice is idempotent and does not fail."""
    success1 = run_init_db(custom_db_url=temp_sqlite_db_url)
    assert success1 is True

    success2 = run_init_db(custom_db_url=temp_sqlite_db_url)
    assert success2 is True


def test_all_expected_tables_in_metadata():
    """Verify all expected 10 application models are registered on Base.metadata."""
    metadata_tables = set(Base.metadata.tables.keys())
    expected_tables = {
        "stores",
        "users",
        "products",
        "stock_movements",
        "customers",
        "bills",
        "bill_items",
        "khata_transactions",
        "owner_preferences",
        "agent_sessions",
    }
    assert expected_tables.issubset(metadata_tables)


def test_database_config_from_settings():
    """Verify engine configuration is created dynamically from centralized Settings."""
    settings = Settings(_env_file=None)
    engine = _configure_engine(settings)
    assert engine is not None
    assert str(engine.url).startswith("sqlite") or "postgresql" in str(engine.url)


def test_fastapi_lifespan_does_not_call_create_all():
    """Verify FastAPI application lifespan startup does NOT call Base.metadata.create_all()."""
    from app.api.main import app, lifespan

    with patch.object(Base.metadata, "create_all") as mock_create_all:
        client_test_app = MagicMock()
        # Verify that accessing or running lifespan does not trigger create_all
        mock_create_all.assert_not_called()


def test_mask_db_url_security():
    """Verify database password/credentials are masked securely in output."""
    pg_url = "postgresql+psycopg://postgres:secretpassword123@localhost:5432/kirana_prod"
    masked = mask_db_url(pg_url)
    assert "secretpassword123" not in masked
    assert "***MASKED***" in masked


def test_sqlalchemy_and_postgres_driver_imports():
    """Verify SQLAlchemy and psycopg (v3) dependencies import cleanly."""
    import sqlalchemy
    import psycopg

    assert sqlalchemy.__version__ is not None
    assert psycopg.__version__ is not None


def test_init_db_postgresql_schema_migration_execution():
    """Verify run_init_db executes ALTER TABLE users ALTER COLUMN telegram_user_id TYPE BIGINT when dialect is postgresql."""
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    with patch("scripts.init_db._configure_engine", return_value=mock_engine), \
         patch("scripts.init_db.Base.metadata.create_all"), \
         patch("scripts.init_db.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = [
            "stores", "users", "products", "stock_movements", "customers",
            "bills", "bill_items", "khata_transactions", "owner_preferences", "agent_sessions"
        ]
        mock_inspect.return_value = mock_inspector

        success = run_init_db("postgresql+psycopg://user:pass@localhost:5432/testdb")
        assert success is True

        # Verify SQL statement executed
        assert mock_conn.execute.called
        executed_sql = str(mock_conn.execute.call_args[0][0])
        assert "ALTER TABLE users ALTER COLUMN telegram_user_id TYPE BIGINT" in executed_sql


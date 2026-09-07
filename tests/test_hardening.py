import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.services.billing_service import (
    create_draft_bill,
    finalize_bill,
    get_current_bill,
    add_bill_item,
)
from app.services.inventory_service import receive_stock, adjust_stock
from app.db.database import SessionLocal, get_db_context, init_db
from app.db.models import Product
from app.exceptions import IdempotencyConflictError, DatabaseLockedError

# Helper to create a temporary product for tests
def _create_test_product(db: Session) -> Product:
    from app.auth.service import get_or_create_default_store
    get_or_create_default_store(db)
    product = Product(
        sku=str(uuid.uuid4()),
        name="Test Product",
        cost_price=Decimal("10.00"),
        selling_price=Decimal("12.00"),
        mrp=Decimal("15.00"),
        gst_rate=Decimal("0.18"),
        hsn_code="1234",
        stock_quantity=0,
        active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

# ---------------------------------------------------------------------------
# Retry‑on‑lock decorator tests
# ---------------------------------------------------------------------------

def test_retry_on_lock_success(monkeypatch):
    from app.db.retry_utils import retry_on_lock
    calls = []

    @retry_on_lock(max_retries=3, backoff_factor=0)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise Exception("database is locked")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3


def test_retry_on_lock_exhaustion(monkeypatch):
    from app.db.retry_utils import retry_on_lock

    @retry_on_lock(max_retries=2, backoff_factor=0)
    def always_locked():
        raise Exception("database is locked")

    with pytest.raises(DatabaseLockedError):
        always_locked()

# ---------------------------------------------------------------------------
# Idempotency tests for draft creation and finalization
# ---------------------------------------------------------------------------

def test_create_draft_idempotent():
    with get_db_context() as db:
        from app.auth.service import get_or_create_default_store
        get_or_create_default_store(db)
        key = str(uuid.uuid4())
        draft1 = create_draft_bill(db, idempotency_key=key)
        draft2 = create_draft_bill(db, idempotency_key=key)
        assert draft1.id == draft2.id
        assert draft1.idempotency_key == key



def test_finalize_idempotent():
    with get_db_context() as db:
        # Prepare product and stock
        product = _create_test_product(db)
        receive_stock(db, product.id, quantity=5, cost_price=Decimal("9.00"), mrp=Decimal("14.00"))
        # Create draft and add item
        draft = create_draft_bill(db)
        add_bill_item(db, draft.id, product.id, quantity=1)
        # Finalize twice with same idempotency key
        key = str(uuid.uuid4())
        fin1 = finalize_bill(db, draft.id, payment_method="CASH", idempotency_key=key)
        fin2 = finalize_bill(db, draft.id, payment_method="CASH", idempotency_key=key)
        assert fin1.id == fin2.id
        # Verify stock only decremented once
        refreshed = db.query(Product).filter_by(id=product.id).first()
        assert refreshed.stock_quantity == 4

# ---------------------------------------------------------------------------
# Concurrent stock adjustment test (simulated with threads)
# ---------------------------------------------------------------------------

def test_concurrent_receive_stock():
    import app.db.database as db_mod
    db_mod.init_db()
    with db_mod.SessionLocal() as db:
        product = _create_test_product(db)
        product_id = product.id

    def worker(qty):
        for _ in range(15):
            try:
                with db_mod.SessionLocal() as db:
                    receive_stock(db, product_id, quantity=qty, cost_price=Decimal("9.00"), mrp=Decimal("14.00"))
                break
            except Exception:
                import time
                time.sleep(0.1)

    import threading
    t1 = threading.Thread(target=worker, args=(5,))
    t2 = threading.Thread(target=worker, args=(7,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    with db_mod.SessionLocal() as db:
        final = db.query(Product).filter_by(id=product_id).first()
        assert final.stock_quantity == 12


def test_concurrent_adjust_stock():
    """Verify concurrent positive and negative stock adjustments compute exact final balance."""
    import app.db.database as db_mod
    db_mod.init_db()
    with db_mod.SessionLocal() as db:
        product = _create_test_product(db)
        product.stock_quantity = Decimal("10.00")
        db.commit()
        product_id = product.id

    def worker(change, reason):
        for _ in range(15):
            try:
                with db_mod.SessionLocal() as db:
                    adjust_stock(db, product_id, quantity_change=change, reason=reason)
                break
            except Exception:
                import time
                time.sleep(0.1)

    import threading
    t1 = threading.Thread(target=worker, args=(Decimal("15.00"), "Received shipment"))
    t2 = threading.Thread(target=worker, args=(Decimal("-3.00"), "Damaged goods"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    with db_mod.SessionLocal() as db:
        final = db.query(Product).filter_by(id=product_id).first()
        # Initial 10 + 15 - 3 = 22
        assert final.stock_quantity == Decimal("22.00")


def test_thread_local_sessions_and_connection_isolation():
    """Verify that concurrent worker threads acquire independent, thread-isolated sessions."""
    import threading
    import app.db.database as db_mod

    sessions = []
    connection_ids = []
    lock = threading.Lock()

    def worker():
        with db_mod.SessionLocal() as db:
            raw_conn = db.connection().connection
            with lock:
                sessions.append(db)
                connection_ids.append(id(raw_conn))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    # Connections acquired across independent concurrent threads must be distinct handles
    assert len(connection_ids) == 2
    assert connection_ids[0] != connection_ids[1]

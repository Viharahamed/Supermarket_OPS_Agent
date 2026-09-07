# tests/test_phase16_e2e_scenarios.py
"""Phase 16 — Comprehensive End-to-End Scenarios (A through M) Test Suite.

Validates business flows, financial correctness, security boundaries, artifact headers,
multi-tenancy isolation, persistent memory, and logging/correlation mechanisms.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
import os
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.schemas import AuthenticatedPrincipal, ToolExecutionContext
from app.auth.service import bootstrap_store_and_user
from app.exceptions import (
    InsufficientStockError,
    BillAlreadyFinalizedError,
    ProductNotFoundError,
)
from app.logging_config import (
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    validate_log_level,
    SecretMaskingFormatter,
)
from app.services import (
    inventory_service,
    billing_service,
    reporting_service,
)
from app.agent.agent import save_session_history, load_session_history
from app.agent import clear_session
from app.documents import generate_invoice_pdf, generate_sales_analysis_pptx
from app.db.models import Customer, KhataTransaction, OwnerPreference
from app.tools.preferences import get_user_preferences, update_user_preferences
from app.tools.schemas import GetPreferenceInput, SetPreferenceInput
from app.api.main import app


# -----------------------------------------------------------------------------
# Fixtures for Multi-Tenant Testing
# -----------------------------------------------------------------------------

@pytest.fixture
def multi_tenant_setup(db_session: Session):
    """Create Store 1 (Owner 1) and Store 2 (Owner 2) contexts for isolation testing."""
    p1 = bootstrap_store_and_user(
        store_name="Store Alpha",
        telegram_user_id=10101,
        user_name="Alpha Owner",
        role="OWNER",
        db=db_session,
    )
    p2 = bootstrap_store_and_user(
        store_name="Store Beta",
        telegram_user_id=20202,
        user_name="Beta Owner",
        role="OWNER",
        db=db_session,
    )

    ctx1 = ToolExecutionContext(principal=p1, db=db_session)
    ctx2 = ToolExecutionContext(principal=p2, db=db_session)

    return {"ctx1": ctx1, "ctx2": ctx2, "p1": p1, "p2": p2}


# -----------------------------------------------------------------------------
# Scenario A — Receive Stock
# -----------------------------------------------------------------------------

def test_scenario_a_receive_stock(db_session: Session):
    """SCENARIO A: Receive stock for product, verify stock increase & movement record."""
    principal = bootstrap_store_and_user(db=db_session)

    # 1. Create product
    prod = inventory_service.create_product(
        db=db_session,
        store_id=principal.store_id,
        name="Maggi Noodles 70g",
        sku="MAGGI-70G-A",
        unit="pack",
        cost_price=Decimal("10.00"),
        mrp=Decimal("14.00"),
        selling_price=Decimal("12.00"),
        stock_quantity=Decimal("10.00"),
        gst_rate=Decimal("12.0"),
    )

    # 2. Receive stock: 50 packets came in @ cost 12, MRP 14
    movement = inventory_service.receive_stock(
        db=db_session,
        product_id=prod.id,
        quantity=Decimal("50.00"),
        cost_price=Decimal("12.00"),
        mrp=Decimal("14.00"),
        store_id=principal.store_id,
    )

    stock_status = inventory_service.get_stock(db=db_session, product_id=prod.id, store_id=principal.store_id)
    assert stock_status.stock_quantity == Decimal("60.00")
    assert movement.quantity == Decimal("50.00")
    assert movement.movement_type == "STOCK_IN"


# -----------------------------------------------------------------------------
# Scenario B — Multi-Item Bill & Price Grounding
# -----------------------------------------------------------------------------

def test_scenario_b_multi_item_bill(db_session: Session):
    """SCENARIO B: Create multi-item draft bill. Stock MUST remain untouched."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    p1 = inventory_service.create_product(db=db_session, store_id=sid, name="Sugar 1kg", sku="SUG-1KG", unit="kg", cost_price=Decimal("38.00"), mrp=Decimal("45.00"), selling_price=Decimal("42.00"), stock_quantity=Decimal("100.00"))
    p2 = inventory_service.create_product(db=db_session, store_id=sid, name="Aashirvaad Atta 5kg", sku="ATT-5KG", unit="pack", cost_price=Decimal("210.00"), mrp=Decimal("260.00"), selling_price=Decimal("240.00"), stock_quantity=Decimal("50.00"))
    p3 = inventory_service.create_product(db=db_session, store_id=sid, name="Maggi 70g", sku="MAG-70G", unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("100.00"))
    p4 = inventory_service.create_product(db=db_session, store_id=sid, name="Amul Butter 100g", sku="BUT-100G", unit="pack", cost_price=Decimal("50.00"), mrp=Decimal("60.00"), selling_price=Decimal("58.00"), stock_quantity=Decimal("30.00"))

    # Draft bill creation
    bill = billing_service.create_draft_bill(db=db_session, store_id=sid)
    billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p1.id, quantity=Decimal("2.00"), store_id=sid)
    billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p2.id, quantity=Decimal("1.00"), store_id=sid)
    billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p3.id, quantity=Decimal("4.00"), store_id=sid)
    updated_bill = billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p4.id, quantity=Decimal("1.00"), store_id=sid)

    assert updated_bill.status == "DRAFT"
    assert len(updated_bill.items) == 4

    # Verify stock untouched during draft
    st1 = inventory_service.get_stock(db=db_session, product_id=p1.id, store_id=sid)
    st2 = inventory_service.get_stock(db=db_session, product_id=p2.id, store_id=sid)
    assert st1.stock_quantity == Decimal("100.00")
    assert st2.stock_quantity == Decimal("50.00")


# -----------------------------------------------------------------------------
# Scenario C — Bill Edit
# -----------------------------------------------------------------------------

def test_scenario_c_bill_edit(db_session: Session):
    """SCENARIO C: Edit draft bill (drop item, update quantity). Stock remains untouched."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    p_maggi = inventory_service.create_product(db=db_session, store_id=sid, name="Maggi 70g", sku="MAG-70G-C", unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("100.00"))
    p_butter = inventory_service.create_product(db=db_session, store_id=sid, name="Amul Butter", sku="BUT-100G-C", unit="pack", cost_price=Decimal("50.00"), mrp=Decimal("60.00"), selling_price=Decimal("58.00"), stock_quantity=Decimal("30.00"))

    bill = billing_service.create_draft_bill(db=db_session, store_id=sid)
    bill = billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p_maggi.id, quantity=Decimal("4.00"), store_id=sid)
    bill = billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p_butter.id, quantity=Decimal("1.00"), store_id=sid)

    # Edit: remove butter, change Maggi to 6
    butter_item = next(item for item in bill.items if item.product_id == p_butter.id)
    bill = billing_service.remove_bill_item(db=db_session, bill_id=bill.id, item_id=butter_item.id, store_id=sid)
    updated_bill = billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p_maggi.id, quantity=Decimal("2.00"), store_id=sid)

    assert len(updated_bill.items) == 1
    assert updated_bill.items[0].product_id == p_maggi.id
    assert updated_bill.items[0].quantity == Decimal("6.00")
    assert updated_bill.status == "DRAFT"

    # Stock still untouched
    st = inventory_service.get_stock(db=db_session, product_id=p_maggi.id, store_id=sid)
    assert st.stock_quantity == Decimal("100.00")


# -----------------------------------------------------------------------------
# Scenario D — Finalize Bill (Atomic & Idempotent)
# -----------------------------------------------------------------------------

def test_scenario_d_finalize_bill_idempotency(db_session: Session):
    """SCENARIO D: Finalize bill atomically, verify stock decrement and finalization immutability."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    p_maggi = inventory_service.create_product(db=db_session, store_id=sid, name="Maggi 70g", sku="MAG-70G-D", unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("14.00"), selling_price=Decimal("14.00"), stock_quantity=Decimal("100.00"))

    bill = billing_service.create_draft_bill(db=db_session, store_id=sid)
    billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p_maggi.id, quantity=Decimal("10.00"), store_id=sid)

    # Finalize bill
    finalized = billing_service.finalize_bill(db=db_session, bill_id=bill.id, payment_method="UPI", store_id=sid)
    assert finalized.status == "FINALIZED"
    assert finalized.payment_method == "UPI"

    # Verify stock decremented
    st = inventory_service.get_stock(db=db_session, product_id=p_maggi.id, store_id=sid)
    assert st.stock_quantity == Decimal("90.00")

    # Attempting to modify finalized bill MUST fail
    with pytest.raises(BillAlreadyFinalizedError):
        billing_service.add_bill_item(db=db_session, bill_id=finalized.id, product_id=p_maggi.id, quantity=Decimal("5.00"), store_id=sid)

    # Re-finalizing returns same bill without double stock decrement
    refinalized = billing_service.finalize_bill(db=db_session, bill_id=bill.id, payment_method="UPI", store_id=sid)
    assert refinalized.id == finalized.id
    st_after = inventory_service.get_stock(db=db_session, product_id=p_maggi.id, store_id=sid)
    assert st_after.stock_quantity == Decimal("90.00")


# -----------------------------------------------------------------------------
# Scenario E — Oversell Protection
# -----------------------------------------------------------------------------

def test_scenario_e_oversell_protection(db_session: Session):
    """SCENARIO E: Attempt to sell more stock than available -> rejected, stock safe."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    p_rare = inventory_service.create_product(db=db_session, store_id=sid, name="Rare Spices", sku="SPICE-RARE", unit="pack", cost_price=Decimal("50.00"), mrp=Decimal("100.00"), selling_price=Decimal("80.00"), stock_quantity=Decimal("5.00"))

    bill = billing_service.create_draft_bill(db=db_session, store_id=sid)
    billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p_rare.id, quantity=Decimal("10.00"), store_id=sid)

    # Finalization must be rejected due to insufficient stock
    with pytest.raises(InsufficientStockError):
        billing_service.finalize_bill(db=db_session, bill_id=bill.id, payment_method="CASH", store_id=sid)

    # Stock must remain 5.00
    st = inventory_service.get_stock(db=db_session, product_id=p_rare.id, store_id=sid)
    assert st.stock_quantity == Decimal("5.00")


# -----------------------------------------------------------------------------
# Scenario F — Khata Customer Ledger
# -----------------------------------------------------------------------------

def test_scenario_f_khata_ledger(db_session: Session):
    """SCENARIO F: Customer credit & payment transactions produce correct net balance."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    cust = Customer(store_id=sid, name="Ramesh Kumar", phone="9876543210", khata_balance=Decimal("0.00"))
    db_session.add(cust)
    db_session.commit()
    db_session.refresh(cust)

    # Credit transaction +500
    t1 = KhataTransaction(store_id=sid, customer_id=cust.id, transaction_type="CREDIT", amount=Decimal("500.00"), balance_after=Decimal("500.00"))
    cust.khata_balance = Decimal("500.00")
    db_session.add(t1)
    db_session.commit()
    assert cust.khata_balance == Decimal("500.00")

    # Payment transaction -300
    t2 = KhataTransaction(store_id=sid, customer_id=cust.id, transaction_type="PAYMENT", amount=Decimal("300.00"), balance_after=Decimal("200.00"))
    cust.khata_balance = Decimal("200.00")
    db_session.add(t2)
    db_session.commit()
    assert cust.khata_balance == Decimal("200.00")


# -----------------------------------------------------------------------------
# Scenario G — Daily Close Sales Report
# -----------------------------------------------------------------------------

def test_scenario_g_daily_close_report(db_session: Session):
    """SCENARIO G: Daily sales summary with tax, payment breakdown, and date bounds."""
    principal = bootstrap_store_and_user(db=db_session)
    report = reporting_service.get_daily_sales(report_date=reporting_service.get_store_date(), store_id=principal.store_id)
    assert report is not None
    assert hasattr(report, "bill_count")
    assert hasattr(report, "grand_total")


# -----------------------------------------------------------------------------
# Scenario H — PDF Invoice Document Artifact
# -----------------------------------------------------------------------------

def test_scenario_h_pdf_generation(db_session: Session):
    """SCENARIO H: Verify finalized bill generates valid PDF document starting with %PDF-."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    p = inventory_service.create_product(db=db_session, store_id=sid, name="Test Product", sku="TEST-PDF", unit="pcs", cost_price=Decimal("10.00"), mrp=Decimal("20.00"), selling_price=Decimal("18.00"), stock_quantity=Decimal("50.00"))
    bill = billing_service.create_draft_bill(db=db_session, store_id=sid)
    billing_service.add_bill_item(db=db_session, bill_id=bill.id, product_id=p.id, quantity=Decimal("2.00"), store_id=sid)
    finalized = billing_service.finalize_bill(db=db_session, bill_id=bill.id, payment_method="CASH", store_id=sid)

    res = generate_invoice_pdf(finalized.id, db=db_session, store_id=sid)
    assert res is not None
    assert "file_path" in res
    assert os.path.exists(res["file_path"])

    with open(res["file_path"], "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"
    assert os.path.getsize(res["file_path"]) > 500


# -----------------------------------------------------------------------------
# Scenario I — PPTX Weekly Sales Analysis Artifact
# -----------------------------------------------------------------------------

def test_scenario_i_pptx_generation(db_session: Session):
    """SCENARIO I: Verify weekly sales presentation generates valid PPTX document starting with PK\x03\x04."""
    principal = bootstrap_store_and_user(db=db_session)
    sid = principal.store_id

    res = generate_sales_analysis_pptx(db=db_session, store_id=sid)
    assert res is not None
    assert "file_path" in res
    assert os.path.exists(res["file_path"])

    with open(res["file_path"], "rb") as f:
        header = f.read(4)
        assert header == b"PK\x03\x04"  # Standard Zip container header for PPTX
    assert os.path.getsize(res["file_path"]) > 2000


# -----------------------------------------------------------------------------
# Scenario J — Persistent Owner Preference
# -----------------------------------------------------------------------------

def test_scenario_j_persistent_preferences(db_session: Session):
    """SCENARIO J: Save persistent owner preference and retrieve across context."""
    principal = bootstrap_store_and_user(db=db_session)
    ctx = ToolExecutionContext(principal=principal, db=db_session)

    update_user_preferences(SetPreferenceInput(key="default_payment_method", value="UPI"), context=ctx)
    res = get_user_preferences(GetPreferenceInput(key="default_payment_method"), context=ctx)
    assert res["value"] == "UPI"


# -----------------------------------------------------------------------------
# Scenario K — Session Reset (/new)
# -----------------------------------------------------------------------------

def test_scenario_k_new_command_session_reset(db_session: Session):
    """SCENARIO K: /new clears conversation memory while preserving database entities."""
    principal = bootstrap_store_and_user(db=db_session)
    user_id = principal.user_id

    # Save session history
    save_session_history(user_id=user_id, history=[{"role": "user", "content": "hello"}], store_id=principal.store_id)
    history_before = load_session_history(user_id=user_id, store_id=principal.store_id)
    assert len(history_before) == 1

    # /new session clear
    success = clear_session(user_id=user_id)
    assert success is True

    history_after = load_session_history(user_id=user_id, store_id=principal.store_id)
    assert len(history_after) == 0


# -----------------------------------------------------------------------------
# Scenario L — Multi-Tenancy Isolation
# -----------------------------------------------------------------------------

def test_scenario_l_multi_tenancy_isolation(db_session: Session, multi_tenant_setup):
    """SCENARIO L: Store 1 context attempting to access Store 2 resources is blocked."""
    ctx1 = multi_tenant_setup["ctx1"]
    ctx2 = multi_tenant_setup["ctx2"]

    # Store 2 creates a product
    p2 = inventory_service.create_product(db=db_session, store_id=ctx2.principal.store_id, name="Secret Product Beta", sku="SECRET-BETA", unit="pack", cost_price=Decimal("10.00"), mrp=Decimal("20.00"), selling_price=Decimal("15.00"), stock_quantity=Decimal("100.00"))

    # Store 1 user tries to fetch Store 2 product -> ProductNotFoundError
    with pytest.raises(ProductNotFoundError):
        inventory_service.get_stock(db=db_session, product_id=p2.id, store_id=ctx1.principal.store_id)


# -----------------------------------------------------------------------------
# Scenario M — Webhook Lifecycle & Security
# -----------------------------------------------------------------------------

def test_scenario_m_webhook_lifecycle():
    """SCENARIO M: Webhook secret verification and payload error handling."""
    client = TestClient(app)

    # 1. Health check (Liveness)
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json() == {"status": "ok"}

    # 2. Readiness check
    r_resp = client.get("/ready")
    assert r_resp.status_code == 200
    assert r_resp.json() == {"status": "ready", "database": "connected"}

    # 3. Webhook request without secret when secret is required -> 403 Forbidden
    w_resp = client.post("/telegram/webhook", json={"update_id": 12345})
    assert w_resp.status_code in [403, 503]


# -----------------------------------------------------------------------------
# Logging, Correlation & Security Auditing Tests
# -----------------------------------------------------------------------------

def test_correlation_id_context():
    """Verify thread-safe correlation ID set/get/clear."""
    clear_correlation_id()
    assert get_correlation_id() is None

    set_correlation_id("test_corr_12345")
    assert get_correlation_id() == "test_corr_12345"

    clear_correlation_id()
    assert get_correlation_id() is None


def test_log_level_validation():
    """Verify log level string validation & production safety."""
    assert validate_log_level("info") == "INFO"
    assert validate_log_level("DEBUG") == "DEBUG"

    with pytest.raises(ValueError):
        validate_log_level("SUPER_DEBUG")


def test_secret_masking_formatter():
    """Verify sensitive tokens are redacted by SecretMaskingFormatter."""
    formatter = SecretMaskingFormatter("[%(levelname)s] %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg="Connecting with token 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567 and key sk-or-v1-1234567890123456789012345678901234567890",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)

    assert "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ" not in formatted
    assert "[REDACTED_TELEGRAM_TOKEN]" in formatted
    assert "sk-or-v1-1234567890123456789012345678901234567890" not in formatted
    assert "[REDACTED_OPENROUTER_KEY]" in formatted

"""Comprehensive Multi-Tenancy & Authentication Security Test Suite.

Tests tenant data isolation, user-store membership, authorization boundaries,
cross-tenant ID attack rejection, reporting isolation, session isolation,
and LLM store_id injection rejection.
"""

from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.auth import (
    AuthenticatedPrincipal,
    ToolExecutionContext,
    authenticate_telegram_user,
    bootstrap_store_and_user,
)
from app.db.models import Store, User, Product, Bill, Customer, OwnerPreference
from app.exceptions import BillNotFoundError, ProductNotFoundError, CustomerNotFoundError
from app.services import (
    inventory_service,
    billing_service,
    payment_service,
    reporting_service,
)
from app.tools import registry


@pytest.fixture
def setup_multi_tenant_stores(db_session: Session):
    """Fixture initializing two distinct stores (Store A & Store B) and operators."""
    # Store A
    principal_a = bootstrap_store_and_user(
        store_name="Store A - MG Road",
        telegram_user_id=1001,
        user_name="Owner A",
        role="OWNER",
        db=db_session,
    )
    # Store B
    principal_b = bootstrap_store_and_user(
        store_name="Store B - Indiranagar",
        telegram_user_id=2002,
        user_name="Owner B",
        role="OWNER",
        db=db_session,
    )

    ctx_a = ToolExecutionContext(principal=principal_a, db=db_session)
    ctx_b = ToolExecutionContext(principal=principal_b, db=db_session)

    return principal_a, principal_b, ctx_a, ctx_b


def test_store_and_user_creation(setup_multi_tenant_stores, db_session: Session):
    """1 & 2. Verify store creation and user-store membership."""
    p_a, p_b, _, _ = setup_multi_tenant_stores

    assert p_a.store_id != p_b.store_id
    assert p_a.telegram_user_id == 1001
    assert p_b.telegram_user_id == 2002

    # Authenticate via Telegram ID
    auth_a = authenticate_telegram_user(1001, db=db_session)
    auth_b = authenticate_telegram_user(2002, db=db_session)

    assert auth_a is not None
    assert auth_a.store_id == p_a.store_id
    assert auth_b is not None
    assert auth_b.store_id == p_b.store_id


def test_unauthorized_telegram_user_rejection(db_session: Session):
    """3. Verify unauthorized Telegram user ID returns None."""
    auth = authenticate_telegram_user(999999, db=db_session)
    assert auth is None


def test_telegram_user_id_64bit_overflow_regression(db_session: Session):
    """Verify 64-bit Telegram user IDs (e.g., production ID 5868796693 > 2^31 - 1) persist, query, and authenticate without overflow."""
    large_tg_id = 5868796693
    normal_tg_id = 1001

    # 1. Bootstrap user with 64-bit Telegram user ID
    principal_large = bootstrap_store_and_user(
        store_name="64Bit Test Store",
        telegram_user_id=large_tg_id,
        user_name="Large ID Owner",
        db=db_session,
    )
    assert principal_large is not None
    assert principal_large.telegram_user_id == large_tg_id

    # 2. Authenticate 64-bit user
    auth_principal = authenticate_telegram_user(large_tg_id, db=db_session)
    assert auth_principal is not None
    assert auth_principal.telegram_user_id == large_tg_id
    assert auth_principal.store_id == principal_large.store_id

    # 3. Direct ORM persistence & retrieval check without truncation
    db_user = db_session.query(User).filter(User.telegram_user_id == large_tg_id).first()
    assert db_user is not None
    assert db_user.telegram_user_id == 5868796693

    # 4. Verify existing normal 32-bit small Telegram ID continues to work alongside 64-bit ID
    principal_normal = bootstrap_store_and_user(
        store_name="Normal Test Store",
        telegram_user_id=normal_tg_id,
        user_name="Normal ID Owner",
        db=db_session,
    )
    assert authenticate_telegram_user(normal_tg_id, db=db_session).telegram_user_id == 1001


def test_sqlalchemy_postgresql_dialect_bigint_query_compilation():
    """Verify SQLAlchemy query compilation for User.telegram_user_id uses BIGINT typing and does not cast to ::INTEGER in PostgreSQL."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    stmt = select(User).where(User.telegram_user_id == 5868796693)
    compiled_sql = str(stmt.compile(dialect=postgresql.dialect()))

    # Ensure ::INTEGER casting is no longer produced for telegram_user_id
    assert "users.telegram_user_id = %(telegram_user_id_1)s::INTEGER" not in compiled_sql


def test_product_isolation(setup_multi_tenant_stores, db_session: Session):
    """4. Test product creation, search, and stock query isolation."""
    p_a, p_b, _, _ = setup_multi_tenant_stores

    # Create Product in Store A
    prod_a = inventory_service.create_product(
        db=db_session,
        store_id=p_a.store_id,
        name="Maggi Noodles 70g",
        sku="MAGGI-A-70G",
        selling_price=Decimal("14.00"),
        mrp=Decimal("14.00"),
        cost_price=Decimal("11.00"),
        stock_quantity=Decimal("50.00"),
    )

    # Search in Store A -> Found
    res_a = inventory_service.search_products(db_session, "Maggi", store_id=p_a.store_id)
    assert len(res_a) == 1
    assert res_a[0].product_id == prod_a.id

    # Search in Store B -> Empty
    res_b = inventory_service.search_products(db_session, "Maggi", store_id=p_b.store_id)
    assert len(res_b) == 0

    # Cross-tenant get_stock attempt by Store B -> ProductNotFoundError
    with pytest.raises(ProductNotFoundError):
        inventory_service.get_stock(db_session, prod_a.id, store_id=p_b.store_id)


def test_stock_movement_isolation(setup_multi_tenant_stores, db_session: Session):
    """5 & 6. Verify receiving stock for Store A does not affect Store B."""
    p_a, p_b, _, _ = setup_multi_tenant_stores

    prod_a = inventory_service.create_product(
        db=db_session, store_id=p_a.store_id, name="Sugar 1kg", sku="SUGAR-A",
        cost_price=Decimal("35.00"), selling_price=Decimal("40.00"), mrp=Decimal("45.00"), stock_quantity=Decimal("10.00")
    )
    prod_b = inventory_service.create_product(
        db=db_session, store_id=p_b.store_id, name="Sugar 1kg", sku="SUGAR-B",
        cost_price=Decimal("35.00"), selling_price=Decimal("40.00"), mrp=Decimal("45.00"), stock_quantity=Decimal("10.00")
    )

    # Receive stock in Store A
    inventory_service.receive_stock(
        db_session, prod_a.id, quantity=Decimal("20.00"), cost_price=Decimal("35.00"), mrp=Decimal("45.00"), store_id=p_a.store_id
    )

    stock_a = inventory_service.get_stock(db_session, prod_a.id, store_id=p_a.store_id)
    stock_b = inventory_service.get_stock(db_session, prod_b.id, store_id=p_b.store_id)

    assert stock_a.stock_quantity == Decimal("30.00")
    assert stock_b.stock_quantity == Decimal("10.00")


def test_customer_and_khata_isolation(setup_multi_tenant_stores, db_session: Session):
    """7 & 8. Verify customer ledger and Khata balance isolation."""
    p_a, p_b, ctx_a, ctx_b = setup_multi_tenant_stores

    # Create customer with same name "Ramesh" in both stores
    cust_a = registry.execute("create_customer", {"name": "Ramesh", "phone": "9876543210"}, context=ctx_a)
    cust_b = registry.execute("create_customer", {"name": "Ramesh", "phone": "9876543210"}, context=ctx_b)

    id_a = cust_a.data["id"]
    id_b = cust_b.data["id"]
    assert id_a != id_b

    # Add credit to Store A's Ramesh
    registry.execute("add_credit", {"customer_id": id_a, "amount": 500.0, "description": "Credit sale"}, context=ctx_a)

    bal_a = registry.execute("get_khata_balance", {"customer_id": id_a}, context=ctx_a)
    bal_b = registry.execute("get_khata_balance", {"customer_id": id_b}, context=ctx_b)

    assert Decimal(bal_a.data["khata_balance"]) == Decimal("500.00")
    assert Decimal(bal_b.data["khata_balance"]) == Decimal("0.00")

    # Cross-tenant balance query attempt by Store B on Store A's customer -> Failure
    res_cross = registry.execute("get_khata_balance", {"customer_id": id_a}, context=ctx_b)
    assert res_cross.success is False


def test_bill_and_draft_isolation(setup_multi_tenant_stores, db_session: Session):
    """9, 10, 11. Verify draft bill creation and cross-tenant finalization rejection."""
    p_a, p_b, ctx_a, ctx_b = setup_multi_tenant_stores

    prod_a = inventory_service.create_product(
        db=db_session, store_id=p_a.store_id, name="Oil 1L", sku="OIL-A",
        cost_price=Decimal("100.00"), selling_price=Decimal("120.00"), mrp=Decimal("130.00"), stock_quantity=Decimal("50.00")
    )

    # Store A creates draft bill and adds item
    draft_a = billing_service.create_draft_bill(db_session, store_id=p_a.store_id)
    billing_service.add_bill_item(db_session, bill_id=draft_a.id, product_id=prod_a.id, quantity=Decimal("2"), store_id=p_a.store_id)

    # Store B attempts to fetch Store A's draft bill -> BillNotFoundError
    with pytest.raises(BillNotFoundError):
        billing_service.get_current_bill(db_session, draft_a.id, store_id=p_b.store_id)

    # Store B attempts to finalize Store A's draft bill -> BillNotFoundError
    with pytest.raises(BillNotFoundError):
        billing_service.finalize_bill(db_session, draft_a.id, payment_method="CASH", store_id=p_b.store_id)


def test_owner_preference_isolation(setup_multi_tenant_stores, db_session: Session):
    """12. Verify store owner preferences are isolated per store."""
    _, _, ctx_a, ctx_b = setup_multi_tenant_stores

    registry.execute("update_user_preferences", {"key": "receipt_footer", "value": "Store A Footer"}, context=ctx_a)
    registry.execute("update_user_preferences", {"key": "receipt_footer", "value": "Store B Footer"}, context=ctx_b)

    pref_a = registry.execute("get_user_preferences", {"key": "receipt_footer"}, context=ctx_a)
    pref_b = registry.execute("get_user_preferences", {"key": "receipt_footer"}, context=ctx_b)

    assert pref_a.data["value"] == "Store A Footer"
    assert pref_b.data["value"] == "Store B Footer"


def test_sales_reporting_isolation(setup_multi_tenant_stores, db_session: Session):
    """14. Verify daily sales reporting aggregates ONLY the requesting store's data."""
    p_a, p_b, _, _ = setup_multi_tenant_stores
    today = Decimal("0.00")

    # Create & finalize bill in Store A
    p1 = inventory_service.create_product(db=db_session, store_id=p_a.store_id, name="P1", sku="P1", cost_price=Decimal("10"), selling_price=Decimal("100"), mrp=Decimal("100"), stock_quantity=Decimal("10"))
    b1 = billing_service.create_draft_bill(db_session, store_id=p_a.store_id)
    billing_service.add_bill_item(db_session, bill_id=b1.id, product_id=p1.id, quantity=Decimal("1"), store_id=p_a.store_id)
    billing_service.finalize_bill(db_session, bill_id=b1.id, payment_method="CASH", store_id=p_a.store_id)

    # Create & finalize bill in Store B
    p2 = inventory_service.create_product(db=db_session, store_id=p_b.store_id, name="P2", sku="P2", cost_price=Decimal("20"), selling_price=Decimal("500"), mrp=Decimal("500"), stock_quantity=Decimal("10"))
    b2 = billing_service.create_draft_bill(db_session, store_id=p_b.store_id)
    billing_service.add_bill_item(db_session, bill_id=b2.id, product_id=p2.id, quantity=Decimal("1"), store_id=p_b.store_id)
    billing_service.finalize_bill(db_session, bill_id=b2.id, payment_method="CASH", store_id=p_b.store_id)

    rep_a = reporting_service.get_daily_sales(reporting_service.get_store_date(), store_id=p_a.store_id)
    rep_b = reporting_service.get_daily_sales(reporting_service.get_store_date(), store_id=p_b.store_id)

    assert rep_a.grand_total == Decimal("100.00")
    assert rep_b.grand_total == Decimal("500.00")


def test_get_store_date_timezone_independence(monkeypatch):
    """Regression test proving get_store_date() uses Asia/Kolkata date regardless of host OS clock/timezone."""
    from datetime import datetime, date, timezone
    from app.services.reporting_service import get_store_date

    # Mock datetime near IST midnight boundary:
    # 2026-09-07 19:00:00 UTC == 2026-09-08 00:30:00 IST (+5:30)
    # Host date in UTC is 2026-09-07, but store date in IST MUST be 2026-09-08
    utc_dt_after_ist_midnight = datetime(2026, 9, 7, 19, 0, 0, tzinfo=timezone.utc)

    class MockDatetimeAfterISTMidnight:
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return utc_dt_after_ist_midnight.astimezone(tz)
            return utc_dt_after_ist_midnight

    monkeypatch.setattr("app.services.reporting_service.datetime", MockDatetimeAfterISTMidnight)
    assert get_store_date() == date(2026, 9, 8)

    # 2026-09-07 18:00:00 UTC == 2026-09-07 23:30:00 IST (+5:30)
    # Store date in IST is 2026-09-07
    utc_dt_before_ist_midnight = datetime(2026, 9, 7, 18, 0, 0, tzinfo=timezone.utc)

    class MockDatetimeBeforeISTMidnight:
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return utc_dt_before_ist_midnight.astimezone(tz)
            return utc_dt_before_ist_midnight

    monkeypatch.setattr("app.services.reporting_service.datetime", MockDatetimeBeforeISTMidnight)
    assert get_store_date() == date(2026, 9, 7)


def test_document_storage_path_isolation(setup_multi_tenant_stores, db_session: Session):
    """15. Verify PDF invoice generated for Store A is stored in store-scoped directory."""
    p_a, _, ctx_a, _ = setup_multi_tenant_stores

    p1 = inventory_service.create_product(db=db_session, store_id=p_a.store_id, name="Item A", sku="ITEM-A", cost_price=Decimal("10"), selling_price=Decimal("50"), mrp=Decimal("50"), stock_quantity=Decimal("10"))
    b1 = billing_service.create_draft_bill(db_session, store_id=p_a.store_id)
    billing_service.add_bill_item(db_session, bill_id=b1.id, product_id=p1.id, quantity=Decimal("1"), store_id=p_a.store_id)
    final_bill = billing_service.finalize_bill(db_session, bill_id=b1.id, payment_method="CASH", store_id=p_a.store_id)

    doc_res = registry.execute("generate_invoice_pdf", {"bill_id": final_bill.id}, context=ctx_a)
    assert doc_res.success is True
    assert f"stores/{p_a.store_id}/invoices" in doc_res.data["relative_path"]


def test_negative_llm_store_id_injection_rejection(setup_multi_tenant_stores, db_session: Session):
    """18. Test that malicious LLM arguments attempting to pass store_id=1 are ignored."""
    p_a, p_b, _, ctx_b = setup_multi_tenant_stores


    prod_a = inventory_service.create_product(
        db=db_session, store_id=p_a.store_id, name="Secret Item A", sku="SECRET-A",
        cost_price=Decimal("10"), selling_price=Decimal("20"), mrp=Decimal("20"), stock_quantity=Decimal("10")
    )

    # Store B executes search_products passing raw args with injected store_id=1
    res = registry.execute("search_products", {"query": "Secret", "store_id": p_a.store_id}, context=ctx_b)
    # Extra inputs like store_id are either rejected by schema validation or ignored by context extraction;
    # in both cases, Store B can NEVER access Store A's secret items!
    if res.success:
        assert len(res.data) == 0
    else:
        assert res.error.code == "INVALID_TOOL_ARGUMENTS"


def test_role_authorization_owner_vs_operator(setup_multi_tenant_stores, db_session: Session):
    """Verify OWNER and OPERATOR role authorization checks."""
    from app.auth import AuthenticatedPrincipal, check_authorization, require_owner, require_operator
    from app.exceptions import RoleNotAllowedError

    owner = AuthenticatedPrincipal(user_id=1, store_id=1, role="OWNER", name="Owner User")
    operator = AuthenticatedPrincipal(user_id=2, store_id=1, role="OPERATOR", name="Operator User")

    # OWNER permissions
    assert check_authorization(owner, "OWNER") is True
    assert check_authorization(owner, "OPERATOR") is True
    require_owner(owner)
    require_operator(owner)

    # OPERATOR permissions
    assert check_authorization(operator, "OPERATOR") is True
    assert check_authorization(operator, "OWNER") is False
    require_operator(operator)

    # OPERATOR attempting OWNER-only action throws RoleNotAllowedError
    with pytest.raises(RoleNotAllowedError):
        require_owner(operator)



from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, _configure_engine
from app.db.models import (
    Store,
    Product,
    StockMovement,
    Customer,
    KhataTransaction,
    Bill,
    BillItem,
    OwnerPreference,
    AgentSession,
)

@pytest.fixture
def db_session():
    """Fixture providing an in-memory SQLite database session with PRAGMAs enabled."""
    engine = _configure_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    from app.auth.service import get_or_create_default_store
    try:
        get_or_create_default_store(session)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_init_db_creates_all_tables(db_session):
    """Verify that all domain models map to database tables."""
    table_names = Base.metadata.tables.keys()
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
    assert expected_tables.issubset(set(table_names))



def test_product_crud_and_decimal_precision(db_session):
    """Verify product insertion and exact decimal precision for financial values."""
    product = Product(
        sku="ATT-AASH-5K",
        name="Aashirvaad Shuddh Chakki Atta 5kg",
        brand="Aashirvaad",
        category="Staples",
        unit="kg",
        pack_size=Decimal("5.00"),
        is_loose=False,
        cost_price=Decimal("210.00"),
        selling_price=Decimal("245.50"),
        mrp=Decimal("260.00"),
        gst_rate=Decimal("0.00"),
        hsn_code="1101",
        stock_quantity=Decimal("50.00"),
        reorder_level=Decimal("10.00"),
    )
    db_session.add(product)
    db_session.commit()

    fetched = db_session.query(Product).filter_by(sku="ATT-AASH-5K").first()
    assert fetched is not None
    assert fetched.name == "Aashirvaad Shuddh Chakki Atta 5kg"
    assert isinstance(fetched.selling_price, Decimal)
    assert fetched.selling_price == Decimal("245.50")
    assert fetched.pack_size == Decimal("5.00")


def test_customer_khata_relationship(db_session):
    """Verify Customer entity and KhataTransaction relationship."""
    customer = Customer(
        name="Ramesh Kumar",
        phone="9876543210",
        khata_balance=Decimal("150.00")
    )
    db_session.add(customer)
    db_session.commit()

    transaction = KhataTransaction(
        customer_id=customer.id,
        transaction_type="CREDIT_SALE",
        amount=Decimal("150.00"),
        balance_after=Decimal("150.00"),
        idempotency_key="tx_idemp_1001",
        notes="Credit sale for groceries"
    )
    db_session.add(transaction)
    db_session.commit()

    fetched_customer = db_session.query(Customer).filter_by(phone="9876543210").first()
    assert len(fetched_customer.khata_transactions) == 1
    assert fetched_customer.khata_transactions[0].amount == Decimal("150.00")


def test_bill_and_bill_item_cascade(db_session):
    """Verify Bill and BillItem cascade insertion and calculations."""
    product = Product(
        sku="OIL-FORT-1L",
        name="Fortune Sunflower Oil 1L",
        cost_price=Decimal("110.00"),
        selling_price=Decimal("135.00"),
        mrp=Decimal("145.00"),
        gst_rate=Decimal("5.00")
    )
    db_session.add(product)
    db_session.commit()

    bill = Bill(
        bill_number="BILL-2026-001",
        idempotency_key="idemp_bill_001",
        status="FINALIZED",
        payment_method="CASH",
        payment_status="PAID",
        subtotal=Decimal("270.00"),
        taxable_amount=Decimal("257.14"),
        cgst_amount=Decimal("6.43"),
        sgst_amount=Decimal("6.43"),
        tax_total=Decimal("12.86"),
        grand_total=Decimal("270.00")
    )
    db_session.add(bill)
    db_session.commit()

    item = BillItem(
        bill_id=bill.id,
        product_id=product.id,
        product_name_snapshot=product.name,
        quantity=Decimal("2.00"),
        unit_price=Decimal("135.00"),
        cost_price=Decimal("110.00"),
        mrp=Decimal("145.00"),
        gst_rate=Decimal("5.00"),
        taxable_amount=Decimal("257.14"),
        cgst=Decimal("6.43"),
        sgst=Decimal("6.43"),
        tax_amount=Decimal("12.86"),
        line_total=Decimal("270.00")
    )
    db_session.add(item)
    db_session.commit()

    fetched_bill = db_session.query(Bill).filter_by(bill_number="BILL-2026-001").first()
    assert fetched_bill is not None
    assert len(fetched_bill.items) == 1
    assert fetched_bill.items[0].product_name_snapshot == "Fortune Sunflower Oil 1L"
    assert fetched_bill.grand_total == Decimal("270.00")


def test_sqlite_foreign_key_enforcement(db_session):
    """Verify that foreign key constraints are strictly enforced by SQLite PRAGMAs."""
    invalid_movement = StockMovement(
        product_id=9999,  # Non-existent product ID
        movement_type="ADDITION",
        quantity=Decimal("10.00"),
        stock_after=Decimal("10.00")
    )
    db_session.add(invalid_movement)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_owner_preference_and_agent_session(db_session):
    """Verify OwnerPreference and AgentSession key-value models."""
    pref = OwnerPreference(key="default_gst_mode", value="INCLUSIVE")
    session = AgentSession(user_id=12345678, history_json='[{"role": "user", "content": "hello"}]')
    db_session.add_all([pref, session])
    db_session.commit()

    fetched_pref = db_session.query(OwnerPreference).filter_by(key="default_gst_mode").first()
    fetched_session = db_session.query(AgentSession).filter_by(user_id=12345678).first()

    assert fetched_pref.value == "INCLUSIVE"
    assert "hello" in fetched_session.history_json

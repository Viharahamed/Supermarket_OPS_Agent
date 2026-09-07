from decimal import Decimal
import pytest
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, _configure_engine
from app.db.models import Product, Bill, BillItem, StockMovement
from app.exceptions import (
    ProductNotFoundError,
    ProductInactiveError,
    InvalidQuantityError,
    BillNotFoundError,
    BillNotDraftError,
    BillAlreadyFinalizedError,
    EmptyBillError,
    InsufficientStockError,
    BillingError,
)
from app.services import (
    create_draft_bill,
    get_current_bill,
    add_bill_item,
    add_bill_items,
    update_bill_item,
    remove_bill_item,
    calculate_bill,
    finalize_bill,
)


@pytest.fixture
def db_session():
    """Fixture providing an isolated in-memory database session for billing tests."""
    engine = _configure_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    from app.auth.service import get_or_create_default_store
    get_or_create_default_store(session)


    # Seed sample products
    p1 = Product(
        sku="SUGR-FINE-1K",
        name="Uttam Sugar Fine 1kg",
        brand="Uttam",
        category="Staples",
        unit="kg",
        pack_size=Decimal("1.00"),
        cost_price=Decimal("36.00"),
        selling_price=Decimal("42.00"),
        mrp=Decimal("45.00"),
        gst_rate=Decimal("5.00"),
        hsn_code="1701",
        stock_quantity=Decimal("50.00"),
        reorder_level=Decimal("10.00"),
        active=True,
    )
    p2 = Product(
        sku="MAGG-NOOD-70G",
        name="Maggi 2-Minute Masala Noodles 70g",
        brand="Maggi",
        category="Instant Food",
        unit="pack",
        pack_size=Decimal("1.00"),
        cost_price=Decimal("10.00"),
        selling_price=Decimal("14.00"),
        mrp=Decimal("14.00"),
        gst_rate=Decimal("12.00"),
        hsn_code="1902",
        stock_quantity=Decimal("50.00"),
        reorder_level=Decimal("10.00"),
        active=True,
    )
    p3 = Product(
        sku="AMUL-BUTT-100G",
        name="Amul Pasteurised Butter 100g",
        brand="Amul",
        category="Dairy",
        unit="pack",
        pack_size=Decimal("1.00"),
        cost_price=Decimal("48.00"),
        selling_price=Decimal("56.00"),
        mrp=Decimal("58.00"),
        gst_rate=Decimal("12.00"),
        hsn_code="0405",
        stock_quantity=Decimal("20.00"),
        reorder_level=Decimal("5.00"),
        active=True,
    )
    p4 = Product(
        sku="INAC-SOAP-100G",
        name="Inactive Soap 100g",
        brand="OldBrand",
        category="Personal Care",
        unit="piece",
        cost_price=Decimal("10.00"),
        selling_price=Decimal("15.00"),
        mrp=Decimal("15.00"),
        stock_quantity=Decimal("10.00"),
        active=False,
    )
    session.add_all([p1, p2, p3, p4])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# 1. Draft Creation & Retrieval
def test_create_and_get_draft_bill(db_session):
    draft = create_draft_bill(db_session)
    assert draft.id is not None
    assert draft.status == "DRAFT"
    assert draft.grand_total == Decimal("0.00")
    assert len(draft.items) == 0

    fetched = get_current_bill(db_session, draft.id)
    assert fetched.id == draft.id
    assert fetched.status == "DRAFT"


# 2. Add Single & Multiple Items
def test_add_bill_items(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    p2 = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()

    # Add Sugar x 2 (selling_price=42.00, gst=5%)
    # Taxable = 84.00, CGST=2.10, SGST=2.10, Total tax=4.20, Line total=88.20
    b1 = add_bill_item(db_session, draft.id, p1.id, Decimal("2.00"))
    assert len(b1.items) == 1
    assert b1.items[0].product_name_snapshot == "Uttam Sugar Fine 1kg"
    assert b1.items[0].quantity == Decimal("2.00")
    assert b1.items[0].taxable_amount == Decimal("84.00")
    assert b1.items[0].line_total == Decimal("88.20")
    assert b1.grand_total == Decimal("88.20")

    # Add Maggi x 1 (selling_price=14.00, gst=12%)
    # Taxable = 14.00, CGST=0.84, SGST=0.84, Total tax=1.68, Line total=15.68
    b2 = add_bill_item(db_session, draft.id, p2.id, Decimal("1.00"))
    assert len(b2.items) == 2
    assert b2.taxable_amount == Decimal("98.00")  # 84.00 + 14.00
    assert b2.cgst_amount == Decimal("2.94")      # 2.10 + 0.84
    assert b2.sgst_amount == Decimal("2.94")
    assert b2.grand_total == Decimal("103.88")    # 88.20 + 15.68


# 3. Duplicate Product Aggregation
def test_add_duplicate_product_aggregates_quantity(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()

    add_bill_item(db_session, draft.id, p1.id, Decimal("2.00"))
    updated = add_bill_item(db_session, draft.id, p1.id, Decimal("3.00"))

    assert len(updated.items) == 1
    assert updated.items[0].quantity == Decimal("5.00")
    assert updated.items[0].taxable_amount == Decimal("210.00")  # 42.00 * 5
    assert updated.grand_total == Decimal("220.50")            # 210.00 * 1.05


# 4. Invalid Product / Quantity Rejection
def test_add_invalid_product_and_quantity(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    inactive = db_session.query(Product).filter_by(sku="INAC-SOAP-100G").first()

    with pytest.raises(ProductNotFoundError):
        add_bill_item(db_session, draft.id, 99999, Decimal("1.00"))

    with pytest.raises(ProductInactiveError):
        add_bill_item(db_session, draft.id, inactive.id, Decimal("1.00"))

    with pytest.raises(InvalidQuantityError):
        add_bill_item(db_session, draft.id, p1.id, Decimal("0.00"))

    with pytest.raises(InvalidQuantityError):
        add_bill_item(db_session, draft.id, p1.id, Decimal("-5.00"))


# 5. Quantity Editing & Item Removal
def test_update_and_remove_bill_item(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    p2 = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()

    add_bill_item(db_session, draft.id, p1.id, Decimal("2.00"))
    b = add_bill_item(db_session, draft.id, p2.id, Decimal("4.00"))
    item_magg = b.items[1]

    # Update Maggi from 4 to 6
    b_updated = update_bill_item(db_session, draft.id, item_magg.id, Decimal("6.00"))
    assert len(b_updated.items) == 2
    assert b_updated.items[1].quantity == Decimal("6.00")

    # Remove Sugar (item 0)
    item_sugr = b_updated.items[0]
    b_removed = remove_bill_item(db_session, draft.id, item_sugr.id)
    assert len(b_removed.items) == 1
    assert b_removed.items[0].product_id == p2.id


# 6. Draft Operations Do NOT Touch Stock
def test_draft_operations_do_not_touch_stock(db_session):
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    initial_stock = p1.stock_quantity

    draft = create_draft_bill(db_session)
    b1 = add_bill_item(db_session, draft.id, p1.id, Decimal("10.00"))
    db_session.refresh(p1)
    assert p1.stock_quantity == initial_stock

    item_id = b1.items[0].id
    b2 = update_bill_item(db_session, draft.id, item_id, Decimal("20.00"))
    db_session.refresh(p1)
    assert p1.stock_quantity == initial_stock

    remove_bill_item(db_session, draft.id, item_id)
    db_session.refresh(p1)
    assert p1.stock_quantity == initial_stock


# 7. Successful Finalization
def test_finalize_bill_success(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    initial_stock = p1.stock_quantity

    add_bill_item(db_session, draft.id, p1.id, Decimal("5.00"))
    finalized = finalize_bill(db_session, draft.id, payment_method="UPI")

    assert finalized.status == "FINALIZED"
    assert finalized.payment_method == "UPI"
    assert finalized.payment_status == "PAID"

    # Verify stock decremented
    db_session.refresh(p1)
    assert p1.stock_quantity == initial_stock - Decimal("5.00")

    # Verify SALE movement created
    movements = db_session.query(StockMovement).filter_by(product_id=p1.id).all()
    assert len(movements) == 1
    assert movements[0].movement_type == "SALE"
    assert movements[0].quantity == Decimal("-5.00")


# 8. Insufficient Stock Rejection
def test_insufficient_stock_rejection(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="AMUL-BUTT-100G").first()  # Stock is 20.00
    initial_stock = p1.stock_quantity

    # Add 25 items to draft (overselling stock of 20)
    add_bill_item(db_session, draft.id, p1.id, Decimal("25.00"))

    with pytest.raises(InsufficientStockError) as exc_info:
        finalize_bill(db_session, draft.id)

    assert "Amul Pasteurised Butter 100g" in str(exc_info.value)
    assert exc_info.value.requested == "25.00"
    assert exc_info.value.available == "20.00"

    # Verify stock remains unchanged and bill remains DRAFT
    db_session.refresh(p1)
    assert p1.stock_quantity == initial_stock

    bill = db_session.query(Bill).filter_by(id=draft.id).first()
    assert bill.status == "DRAFT"


# 9. Empty Bill Finalization Rejection
def test_finalize_empty_bill_rejection(db_session):
    draft = create_draft_bill(db_session)
    with pytest.raises(EmptyBillError):
        finalize_bill(db_session, draft.id)


# 10. Finalized Bill Immutability
def test_finalized_bill_immutability(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()

    b = add_bill_item(db_session, draft.id, p1.id, Decimal("2.00"))
    item_id = b.items[0].id

    finalize_bill(db_session, draft.id)

    with pytest.raises(BillAlreadyFinalizedError):
        add_bill_item(db_session, draft.id, p1.id, Decimal("1.00"))

    with pytest.raises(BillAlreadyFinalizedError):
        update_bill_item(db_session, draft.id, item_id, Decimal("5.00"))

    with pytest.raises(BillAlreadyFinalizedError):
        remove_bill_item(db_session, draft.id, item_id)


# 11. Idempotency
def test_finalize_bill_idempotency(db_session):
    draft = create_draft_bill(db_session)
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    initial_stock = p1.stock_quantity

    add_bill_item(db_session, draft.id, p1.id, Decimal("5.00"))
    res1 = finalize_bill(db_session, draft.id, idempotency_key="idemp_1001")

    db_session.refresh(p1)
    stock_after_first = p1.stock_quantity
    assert stock_after_first == initial_stock - Decimal("5.00")

    # Second call to finalize_bill
    res2 = finalize_bill(db_session, draft.id, idempotency_key="idemp_1001")

    db_session.refresh(p1)
    assert p1.stock_quantity == stock_after_first  # Stock NOT decremented again
    assert res2.id == res1.id
    assert res2.status == "FINALIZED"

    movements = db_session.query(StockMovement).filter_by(product_id=p1.id).all()
    assert len(movements) == 1  # No duplicate sale movement


# 12. Complete End-to-End Multi-Item Scenario Test (Requirement 25)
def test_end_to_end_multi_item_billing_scenario(db_session):
    p_sugar = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    p_maggi = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    p_butter = db_session.query(Product).filter_by(sku="AMUL-BUTT-100G").first()

    initial_sugar = p_sugar.stock_quantity
    initial_maggi = p_maggi.stock_quantity
    initial_butter = p_butter.stock_quantity

    # Step 1: Create draft
    draft = create_draft_bill(db_session)

    # Step 2: Add Sugar x 2, Maggi x 4, Butter x 1
    add_bill_item(db_session, draft.id, p_sugar.id, Decimal("2.00"))
    add_bill_item(db_session, draft.id, p_maggi.id, Decimal("4.00"))
    b = add_bill_item(db_session, draft.id, p_butter.id, Decimal("1.00"))
    assert len(b.items) == 3

    # Step 3: Remove Butter
    item_butter = next(i for i in b.items if i.product_id == p_butter.id)
    b = remove_bill_item(db_session, draft.id, item_butter.id)
    assert len(b.items) == 2

    # Step 4: Change Maggi from 4 to 6
    item_maggi = next(i for i in b.items if i.product_id == p_maggi.id)
    b = update_bill_item(db_session, draft.id, item_maggi.id, Decimal("6.00"))
    assert len(b.items) == 2
    item_maggi_updated = next(i for i in b.items if i.product_id == p_maggi.id)
    assert item_maggi_updated.quantity == Decimal("6.00")

    # Step 5: Verify stock has NOT changed
    db_session.refresh(p_sugar)
    db_session.refresh(p_maggi)
    db_session.refresh(p_butter)
    assert p_sugar.stock_quantity == initial_sugar
    assert p_maggi.stock_quantity == initial_maggi
    assert p_butter.stock_quantity == initial_butter

    # Step 6: Finalize bill
    finalized = finalize_bill(db_session, draft.id, payment_method="CASH")
    assert finalized.status == "FINALIZED"

    # Step 7: Verify stock decremented exactly once
    db_session.refresh(p_sugar)
    db_session.refresh(p_maggi)
    db_session.refresh(p_butter)
    assert p_sugar.stock_quantity == initial_sugar - Decimal("2.00")
    assert p_maggi.stock_quantity == initial_maggi - Decimal("6.00")
    assert p_butter.stock_quantity == initial_butter  # Butter was removed, stock untouched

    # Step 8: Verify sale stock movements created
    m_sugar = db_session.query(StockMovement).filter_by(product_id=p_sugar.id).first()
    m_maggi = db_session.query(StockMovement).filter_by(product_id=p_maggi.id).first()
    m_butter = db_session.query(StockMovement).filter_by(product_id=p_butter.id).first()

    assert m_sugar is not None and m_sugar.movement_type == "SALE" and m_sugar.quantity == Decimal("-2.00")
    assert m_maggi is not None and m_maggi.movement_type == "SALE" and m_maggi.quantity == Decimal("-6.00")
    assert m_butter is None  # No movement for butter


def test_add_bill_items_batch_success(db_session):
    """Verify batch adding multiple valid items updates bill totals and items deterministically."""
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    p2 = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    draft = create_draft_bill(db_session)

    items_to_add = [
        {"product_id": p1.id, "quantity": Decimal("2.00")},
        {"product_id": p2.id, "quantity": Decimal("4.00")},
    ]

    bill_dto = add_bill_items(db_session, draft.id, items_to_add)
    assert len(bill_dto.items) == 2
    assert bill_dto.grand_total > Decimal("0.00")


def test_add_bill_items_batch_atomic_failure(db_session):
    """Verify batch addition is atomic: if any item is invalid, 0 items are added."""
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    draft = create_draft_bill(db_session)

    items_to_add = [
        {"product_id": p1.id, "quantity": Decimal("2.00")},
        {"product_id": 99999, "quantity": Decimal("1.00")},  # Invalid product ID
    ]

    with pytest.raises(ProductNotFoundError):
        add_bill_items(db_session, draft.id, items_to_add)

    # Verify no items were added to the draft bill
    current_bill = get_current_bill(db_session, draft.id)
    assert len(current_bill.items) == 0


def test_add_bill_items_inactive_product_rejection(db_session):
    """Verify batch addition rejects inactive products atomically."""
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    p2 = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    p2.active = False
    db_session.commit()

    draft = create_draft_bill(db_session)
    items_to_add = [
        {"product_id": p1.id, "quantity": Decimal("2.00")},
        {"product_id": p2.id, "quantity": Decimal("1.00")},
    ]

    with pytest.raises(ProductInactiveError):
        add_bill_items(db_session, draft.id, items_to_add)

    current_bill = get_current_bill(db_session, draft.id)
    assert len(current_bill.items) == 0


def test_add_bill_items_finalized_bill_rejection(db_session):
    """Verify batch addition raises error if bill is already finalized."""
    p1 = db_session.query(Product).filter_by(sku="SUGR-FINE-1K").first()
    draft = create_draft_bill(db_session)
    add_bill_item(db_session, draft.id, p1.id, Decimal("1.00"))
    finalize_bill(db_session, draft.id, payment_method="CASH")

    with pytest.raises(BillAlreadyFinalizedError):
        add_bill_items(db_session, draft.id, [{"product_id": p1.id, "quantity": Decimal("1.00")}])

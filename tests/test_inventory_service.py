from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, _configure_engine
from app.db.models import Product, StockMovement
from app.exceptions import (
    ProductNotFoundError,
    ProductInactiveError,
    InvalidQuantityError,
    InvalidPriceError,
    NegativeStockError,
    InvalidAdjustmentError,
)
from app.services import (
    search_products,
    get_stock,
    get_low_stock,
    receive_stock,
    adjust_stock,
    StockStatus,
)


@pytest.fixture
def db_session():
    """Fixture providing an isolated in-memory database session."""
    engine = _configure_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Seed sample Kirana products
    p1 = Product(
        sku="MAGG-NOOD-70G",
        name="Maggi 2-Minute Masala Noodles 70g",
        brand="Maggi",
        category="Instant Food",
        unit="pack",
        pack_size=Decimal("1.00"),
        cost_price=Decimal("10.00"),
        selling_price=Decimal("14.00"),
        mrp=Decimal("14.00"),
        stock_quantity=Decimal("50.00"),
        reorder_level=Decimal("10.00"),
        active=True,
    )
    p2 = Product(
        sku="AMUL-BUTT-100G",
        name="Amul Pasteurised Butter 100g",
        brand="Amul",
        category="Dairy",
        unit="pack",
        pack_size=Decimal("1.00"),
        cost_price=Decimal("48.00"),
        selling_price=Decimal("56.00"),
        mrp=Decimal("58.00"),
        stock_quantity=Decimal("5.00"),
        reorder_level=Decimal("10.00"),
        active=True,
    )
    p3 = Product(
        sku="PARL-G-250G",
        name="Parle-G Glucose Biscuits 250g",
        brand="Parle",
        category="Snacks",
        unit="pack",
        pack_size=Decimal("1.00"),
        cost_price=Decimal("20.00"),
        selling_price=Decimal("25.00"),
        mrp=Decimal("25.00"),
        stock_quantity=Decimal("0.00"),
        reorder_level=Decimal("15.00"),
        active=True,
    )
    p4 = Product(
        sku="DISC-ITEM-100",
        name="Discontinued Soap 100g",
        brand="OldBrand",
        category="Personal Care",
        unit="piece",
        cost_price=Decimal("10.00"),
        selling_price=Decimal("15.00"),
        mrp=Decimal("15.00"),
        stock_quantity=Decimal("10.00"),
        reorder_level=Decimal("5.00"),
        active=False,
    )
    session.add_all([p1, p2, p3, p4])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# 1. Search existing product
def test_search_existing_product(db_session):
    results = search_products(db_session, "Maggi 2-Minute Masala Noodles 70g")
    assert len(results) == 1
    assert results[0].sku == "MAGG-NOOD-70G"
    assert results[0].name == "Maggi 2-Minute Masala Noodles 70g"


# 2. Search partial product name
def test_search_partial_product_name(db_session):
    results = search_products(db_session, "Maggi")
    assert len(results) == 1
    assert results[0].brand == "Maggi"

    # Search by category
    dairy_results = search_products(db_session, "Dairy")
    assert len(dairy_results) == 1
    assert dairy_results[0].sku == "AMUL-BUTT-100G"


# 3. Search nonexistent product
def test_search_nonexistent_product(db_session):
    results = search_products(db_session, "NonExistentProduct123")
    assert len(results) == 0


# 4. Get stock & stock status classification
def test_get_stock(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    stock_status = get_stock(db_session, product.id)
    assert stock_status.product_id == product.id
    assert stock_status.stock_quantity == Decimal("50.00")
    assert stock_status.unit == "pack"
    assert stock_status.reorder_level == Decimal("10.00")
    assert stock_status.stock_status == StockStatus.IN_STOCK


# 5 & 6. Receive stock & stock quantity increases correctly
def test_receive_stock_success(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    initial_stock = product.stock_quantity

    movement = receive_stock(
        db_session,
        product_id=product.id,
        quantity=Decimal("20.00"),
        cost_price=Decimal("11.00"),
        mrp=Decimal("15.00"),
        reference="INV-2026-001",
        notes="Received fresh batch"
    )

    db_session.refresh(product)
    assert product.stock_quantity == initial_stock + Decimal("20.00")
    assert product.cost_price == Decimal("11.00")
    assert product.mrp == Decimal("15.00")
    assert movement.quantity == Decimal("20.00")
    assert movement.stock_after == product.stock_quantity
    assert movement.movement_type == "STOCK_IN"


# 7. Stock movement record created on receive_stock
def test_receive_stock_movement_created(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    receive_stock(
        db_session,
        product_id=product.id,
        quantity=Decimal("10.00"),
        cost_price=Decimal("10.00"),
        mrp=Decimal("14.00")
    )
    movements = db_session.query(StockMovement).filter_by(product_id=product.id).all()
    assert len(movements) == 1
    assert movements[0].movement_type == "STOCK_IN"
    assert movements[0].quantity == Decimal("10.00")


# 8. Invalid quantity rejected
def test_receive_stock_invalid_quantity(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    with pytest.raises(InvalidQuantityError):
        receive_stock(
            db_session,
            product_id=product.id,
            quantity=Decimal("0.00"),
            cost_price=Decimal("10.00"),
            mrp=Decimal("14.00")
        )
    with pytest.raises(InvalidQuantityError):
        receive_stock(
            db_session,
            product_id=product.id,
            quantity=Decimal("-5.00"),
            cost_price=Decimal("10.00"),
            mrp=Decimal("14.00")
        )


# 9. Invalid price rejected
def test_receive_stock_invalid_price(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    # Negative cost price
    with pytest.raises(InvalidPriceError):
        receive_stock(
            db_session,
            product_id=product.id,
            quantity=Decimal("10.00"),
            cost_price=Decimal("-1.00"),
            mrp=Decimal("14.00")
        )
    # Cost price greater than MRP
    with pytest.raises(InvalidPriceError):
        receive_stock(
            db_session,
            product_id=product.id,
            quantity=Decimal("10.00"),
            cost_price=Decimal("20.00"),
            mrp=Decimal("14.00")
        )


# 10. Stock adjustment positive
def test_adjust_stock_positive(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    initial_stock = product.stock_quantity

    movement = adjust_stock(
        db_session,
        product_id=product.id,
        quantity_change=Decimal("5.00"),
        reason="Inventory audit discrepancy found extra items"
    )

    db_session.refresh(product)
    assert product.stock_quantity == initial_stock + Decimal("5.00")
    assert movement.movement_type == "ADJUSTMENT"
    assert movement.quantity == Decimal("5.00")
    assert movement.notes == "Inventory audit discrepancy found extra items"


# 11. Stock adjustment negative
def test_adjust_stock_negative(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    initial_stock = product.stock_quantity

    movement = adjust_stock(
        db_session,
        product_id=product.id,
        quantity_change=Decimal("-5.00"),
        reason="Damaged packs found during inspection"
    )

    db_session.refresh(product)
    assert product.stock_quantity == initial_stock - Decimal("5.00")
    assert movement.quantity == Decimal("-5.00")


# 12. Negative stock rejected (service layer & DB constraint)
def test_negative_stock_rejected(db_session):
    product = db_session.query(Product).filter_by(sku="AMUL-BUTT-100G").first()
    # Current stock is 5.00, adjusting by -10.00 must raise NegativeStockError
    with pytest.raises(NegativeStockError):
        adjust_stock(
            db_session,
            product_id=product.id,
            quantity_change=Decimal("-10.00"),
            reason="Attempting over-reduction"
        )

    db_session.refresh(product)
    assert product.stock_quantity == Decimal("5.00")

    # Verify DB constraint directly
    product.stock_quantity = Decimal("-1.00")
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 13. Failed transaction does not partially update database
def test_failed_transaction_atomicity(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    initial_stock = product.stock_quantity
    initial_cost = product.cost_price

    # Invalid operation (cost > mrp)
    with pytest.raises(InvalidPriceError):
        receive_stock(
            db_session,
            product_id=product.id,
            quantity=Decimal("100.00"),
            cost_price=Decimal("50.00"),
            mrp=Decimal("30.00")
        )

    db_session.refresh(product)
    assert product.stock_quantity == initial_stock
    assert product.cost_price == initial_cost
    # Verify no stock movement was logged
    movements = db_session.query(StockMovement).filter_by(product_id=product.id).all()
    assert len(movements) == 0


# 14. Low-stock detection
def test_low_stock_detection(db_session):
    low_stock_items = get_low_stock(db_session)
    sku_list = [item.sku for item in low_stock_items]
    # Amul Butter (stock 5, reorder 10) and Parle-G (stock 0, reorder 15) should be detected
    assert "AMUL-BUTT-100G" in sku_list
    assert "PARL-G-250G" in sku_list
    # Maggi (stock 50, reorder 10) should NOT be in low stock
    assert "MAGG-NOOD-70G" not in sku_list


# 15. Out-of-stock detection
def test_out_of_stock_detection(db_session):
    parle_g = db_session.query(Product).filter_by(sku="PARL-G-250G").first()
    stock_status = get_stock(db_session, parle_g.id)
    assert stock_status.stock_status == StockStatus.OUT_OF_STOCK


# Additional tests: Nonexistent & inactive product handling
def test_nonexistent_and_inactive_product(db_session):
    with pytest.raises(ProductNotFoundError):
        get_stock(db_session, 99999)

    inactive_product = db_session.query(Product).filter_by(sku="DISC-ITEM-100").first()
    with pytest.raises(ProductInactiveError):
        receive_stock(db_session, inactive_product.id, Decimal("10"), Decimal("10"), Decimal("15"))

    with pytest.raises(ProductInactiveError):
        adjust_stock(db_session, inactive_product.id, Decimal("5"), "Audit")


# Additional test: Adjustment without reason rejected
def test_adjust_stock_requires_reason(db_session):
    product = db_session.query(Product).filter_by(sku="MAGG-NOOD-70G").first()
    with pytest.raises(InvalidAdjustmentError):
        adjust_stock(db_session, product.id, Decimal("5.00"), reason="")

from decimal import Decimal, InvalidOperation
from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import Product, StockMovement
from app.exceptions import (
    ProductNotFoundError,
    ProductInactiveError,
    InvalidQuantityError,
    InvalidPriceError,
    NegativeStockError,
    InvalidAdjustmentError,
)
from app.db.retry_utils import retry_on_lock
from app.services.schemas import (
    ProductDTO,
    StockStatusDTO,
    StockStatus,
    StockMovementDTO,
)


def _to_decimal(value: str | float | int | Decimal, param_name: str) -> Decimal:
    """Helper to safely parse and convert values to Decimal."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        raise InvalidQuantityError(f"Invalid decimal value for '{param_name}': {value}")


def product_to_dto(product: Product) -> ProductDTO:
    """Map Product ORM entity to ProductDTO."""
    return ProductDTO(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        brand=product.brand,
        category=product.category,
        unit=product.unit,
        pack_size=product.pack_size,
        is_loose=product.is_loose,
        cost_price=product.cost_price,
        selling_price=product.selling_price,
        mrp=product.mrp,
        gst_rate=product.gst_rate,
        hsn_code=product.hsn_code,
        stock_quantity=product.stock_quantity,
        reorder_level=product.reorder_level,
        active=product.active,
    )


def product_to_stock_status_dto(product: Product) -> StockStatusDTO:
    """Calculate stock status and map Product ORM entity to StockStatusDTO."""
    if product.stock_quantity <= Decimal("0.00"):
        status = StockStatus.OUT_OF_STOCK
    elif product.stock_quantity <= product.reorder_level:
        status = StockStatus.LOW_STOCK
    else:
        status = StockStatus.IN_STOCK

    return StockStatusDTO(
        product_id=product.id,
        product_name=product.name,
        sku=product.sku,
        stock_quantity=product.stock_quantity,
        unit=product.unit,
        reorder_level=product.reorder_level,
        stock_status=status,
        product=product_to_dto(product),
    )


def stock_movement_to_dto(movement: StockMovement) -> StockMovementDTO:
    """Map StockMovement ORM entity to StockMovementDTO."""
    return StockMovementDTO(
        id=movement.id,
        product_id=movement.product_id,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        stock_after=movement.stock_after,
        reference_id=movement.reference_id,
        notes=movement.notes,
        created_at=movement.created_at,
    )


def search_products(
    db: Session,
    query: str,
    include_inactive: bool = False
) -> List[ProductDTO]:
    """
    Search active products by name, brand, SKU, or category using partial matching.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    pattern = f"%{cleaned_query}%"
    db_query = db.query(Product).filter(
        or_(
            Product.name.ilike(pattern),
            Product.brand.ilike(pattern),
            Product.sku.ilike(pattern),
            Product.category.ilike(pattern),
        )
    )

    if not include_inactive:
        db_query = db_query.filter(Product.active.is_(True))

    products = db_query.all()
    return [product_to_dto(p) for p in products]


def get_stock(db: Session, product_id: int) -> StockStatusDTO:
    """
    Fetch product and evaluate its deterministic stock status.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ProductNotFoundError(product_id)

    return product_to_stock_status_dto(product)


def get_low_stock(db: Session) -> List[StockStatusDTO]:
    """
    Retrieve all active products where stock_quantity <= reorder_level.
    """
    products = (
        db.query(Product)
        .filter(
            Product.active.is_(True),
            Product.stock_quantity <= Product.reorder_level,
        )
        .order_by(Product.stock_quantity.asc())
        .all()
    )
    return [product_to_stock_status_dto(p) for p in products]


@retry_on_lock()
def receive_stock(
    db: Session,
    product_id: int,
    quantity: Decimal | float | str,
    cost_price: Decimal | float | str,
    mrp: Decimal | float | str,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> StockMovementDTO:
    """
    Receive stock for an active product, updating cost_price and MRP, logging a STOCK_IN movement.
    """
    qty_dec = _to_decimal(quantity, "quantity")
    cost_dec = _to_decimal(cost_price, "cost_price")
    mrp_dec = _to_decimal(mrp, "mrp")

    if qty_dec <= Decimal("0.00"):
        raise InvalidQuantityError("Received stock quantity must be strictly greater than 0.")
    if cost_dec <= Decimal("0.00"):
        raise InvalidPriceError("Cost price must be strictly greater than 0.")
    if mrp_dec <= Decimal("0.00"):
        raise InvalidPriceError("MRP must be strictly greater than 0.")
    if cost_dec > mrp_dec:
        raise InvalidPriceError(f"Cost price ({cost_dec}) cannot be greater than MRP ({mrp_dec}).")

    try:
        product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
        if not product:
            raise ProductNotFoundError(product_id)
        if not product.active:
            raise ProductInactiveError(product_id)

        db.query(Product).filter(Product.id == product_id).update(
            {
                Product.cost_price: cost_dec,
                Product.mrp: mrp_dec,
                Product.stock_quantity: Product.stock_quantity + qty_dec,
            },
            synchronize_session="fetch",
        )
        db.refresh(product)

        # Create movement record
        movement = StockMovement(
            product_id=product.id,
            movement_type="STOCK_IN",
            quantity=qty_dec,
            stock_after=product.stock_quantity,
            reference_id=reference,
            notes=notes or f"Received stock: +{qty_dec} {product.unit}",
        )
        db.add(movement)
        db.commit()
        db.refresh(movement)
        return stock_movement_to_dto(movement)
    except Exception:
        db.rollback()
        raise


@retry_on_lock()
def adjust_stock(
    db: Session,
    product_id: int,
    quantity_change: Decimal | float | str,
    reason: str,
    reference: Optional[str] = None,
) -> StockMovementDTO:
    """
    Perform a controlled stock adjustment (positive or negative) with mandatory audit reason.
    """
    if not reason or not reason.strip():
        raise InvalidAdjustmentError("Adjustment reason is required and cannot be empty.")

    change_dec = _to_decimal(quantity_change, "quantity_change")
    if change_dec == Decimal("0.00"):
        raise InvalidQuantityError("Stock adjustment quantity change cannot be zero.")

    try:
        product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
        if not product:
            raise ProductNotFoundError(product_id)
        if not product.active:
            raise ProductInactiveError(product_id)

        new_stock = product.stock_quantity + change_dec
        if new_stock < Decimal("0.00"):
            raise NegativeStockError(
                current_stock=str(product.stock_quantity),
                requested_change=str(change_dec),
            )

        product.stock_quantity = new_stock

        movement = StockMovement(
            product_id=product.id,
            movement_type="ADJUSTMENT",
            quantity=change_dec,
            stock_after=new_stock,
            reference_id=reference,
            notes=reason.strip(),
        )
        db.add(movement)
        db.commit()
        db.refresh(movement)
        return stock_movement_to_dto(movement)
    except Exception:
        db.rollback()
        raise

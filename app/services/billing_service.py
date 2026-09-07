from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models import Bill, BillItem, Product, StockMovement
from app.db.database import get_db_context
from app.db.retry_utils import retry_on_lock
from app.exceptions import (
    ProductNotFoundError,
    ProductInactiveError,
    InvalidQuantityError,
    InvalidPriceError,
    BillNotFoundError,
    BillNotDraftError,
    BillAlreadyFinalizedError,
    EmptyBillError,
    InsufficientStockError,
    BillingError,
)
from app.services.gst_service import (
    quantize_money,
    validate_pricing,
    calculate_line_item_gst,
    calculate_product_line_item,
)
from app.services.schemas import BillDTO, BillItemDTO


def _generate_bill_number() -> str:
    """Generate unique bill number: BILL-YYYYMMDD-XXXX."""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6].upper()
    return f"BILL-{date_str}-{short_id}"


def bill_item_to_dto(item: BillItem) -> BillItemDTO:
    """Map BillItem ORM entity to BillItemDTO."""
    return BillItemDTO(
        id=item.id,
        bill_id=item.bill_id,
        product_id=item.product_id,
        product_name_snapshot=item.product_name_snapshot,
        quantity=item.quantity,
        unit_price=item.unit_price,
        cost_price=item.cost_price,
        mrp=item.mrp,
        gst_rate=item.gst_rate,
        hsn_code=item.hsn_code,
        taxable_amount=item.taxable_amount,
        cgst=item.cgst,
        sgst=item.sgst,
        tax_amount=item.tax_amount,
        line_total=item.line_total,
        created_at=item.created_at,
    )


def bill_to_dto(bill: Bill) -> BillDTO:
    """Map Bill ORM entity to BillDTO."""
    return BillDTO(
        id=bill.id,
        bill_number=bill.bill_number,
        idempotency_key=bill.idempotency_key,
        status=bill.status,
        customer_id=bill.customer_id,
        payment_method=bill.payment_method,
        payment_status=bill.payment_status,
        subtotal=bill.subtotal,
        taxable_amount=bill.taxable_amount,
        cgst_amount=bill.cgst_amount,
        sgst_amount=bill.sgst_amount,
        tax_total=bill.tax_total,
        discount_amount=bill.discount_amount,
        rounding_amount=bill.rounding_amount,
        grand_total=bill.grand_total,
        items=[bill_item_to_dto(item) for item in bill.items],
        created_at=bill.created_at,
        updated_at=bill.updated_at,
    )


def _recalculate_bill_totals(bill: Bill) -> None:
    """Recalculate and update Bill summary amounts from its BillItems."""
    taxable_sum = Decimal("0.00")
    cgst_sum = Decimal("0.00")
    sgst_sum = Decimal("0.00")
    tax_sum = Decimal("0.00")
    line_total_sum = Decimal("0.00")

    for item in bill.items:
        taxable_sum += item.taxable_amount
        cgst_sum += item.cgst
        sgst_sum += item.sgst
        tax_sum += item.tax_amount
        line_total_sum += item.line_total

    taxable_sum = quantize_money(taxable_sum)
    cgst_sum = quantize_money(cgst_sum)
    sgst_sum = quantize_money(sgst_sum)
    tax_sum = quantize_money(tax_sum)
    grand = quantize_money(line_total_sum)

    bill.subtotal = grand
    bill.taxable_amount = taxable_sum
    bill.cgst_amount = cgst_sum
    bill.sgst_amount = sgst_sum
    bill.tax_total = tax_sum
    bill.grand_total = grand


def create_draft_bill(
    db: Optional[Session] = None,
    customer_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> BillDTO:
    """
    Create a new draft bill. Stock is NOT modified.
    """
    if db is not None and not isinstance(db, Session):
        if isinstance(db, int):
            customer_id = db
        db = None

    def _do_create(session: Session) -> BillDTO:
        if idempotency_key:
            existing = session.query(Bill).filter(Bill.idempotency_key == idempotency_key).first()
            if existing:
                return bill_to_dto(existing)

        bill = Bill(
            bill_number=_generate_bill_number(),
            idempotency_key=idempotency_key,
            status="DRAFT",
            customer_id=customer_id,
            payment_method="PENDING",
            payment_status="UNPAID",
            subtotal=Decimal("0.00"),
            taxable_amount=Decimal("0.00"),
            cgst_amount=Decimal("0.00"),
            sgst_amount=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            rounding_amount=Decimal("0.00"),
            grand_total=Decimal("0.00"),
        )
        session.add(bill)
        session.commit()
        session.refresh(bill)
        return bill_to_dto(bill)

    if db is not None and isinstance(db, Session):
        return _do_create(db)
    else:
        with get_db_context() as session:
            return _do_create(session)


def get_current_bill(
    db: Optional[Session | int] = None,
    bill_id: Optional[int] = None,
) -> BillDTO:
    """
    Retrieve current bill by ID.
    """
    if not isinstance(db, Session):
        if isinstance(db, int):
            bill_id = db
        db = None

    def _do_get(s: Session) -> BillDTO:
        bill = s.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)
        return bill_to_dto(bill)

    if db is not None and isinstance(db, Session):
        return _do_get(db)
    else:
        with get_db_context() as s:
            return _do_get(s)


def add_bill_item(
    db: Optional[Session | int] = None,
    bill_id: Optional[int] = None,
    product_id: Optional[int] = None,
    quantity: Optional[Decimal | float | str] = None,
) -> BillDTO:
    """
    Add product item to draft bill. If product already exists in draft, aggregate quantity.
    Does NOT decrement product stock.
    """
    if not isinstance(db, Session):
        quantity = product_id
        product_id = bill_id
        bill_id = db
        db = None

    def _do_add(s: Session) -> BillDTO:
        try:
            qty = Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity
        except (ValueError, TypeError, InvalidOperation):
            raise InvalidQuantityError(f"Invalid quantity: {quantity}")

        if qty <= Decimal("0.00"):
            raise InvalidQuantityError("Quantity added must be strictly greater than 0.")

        bill = s.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)
        if bill.status == "FINALIZED":
            raise BillAlreadyFinalizedError(bill_id)
        if bill.status != "DRAFT":
            raise BillNotDraftError(bill_id, bill.status)

        product = s.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ProductNotFoundError(product_id)
        if not product.active:
            raise ProductInactiveError(product_id)

        # Validate product pricing
        validate_pricing(product.cost_price, product.selling_price, product.mrp)

        # Check if item already exists in current draft bill
        existing_item = next((item for item in bill.items if item.product_id == product_id), None)

        if existing_item:
            new_qty = existing_item.quantity + qty
            tax_res = calculate_line_item_gst(
                unit_price=existing_item.unit_price,
                quantity=new_qty,
                gst_rate=existing_item.gst_rate,
                hsn_code=existing_item.hsn_code,
            )
            existing_item.quantity = new_qty
            existing_item.taxable_amount = tax_res.taxable_amount
            existing_item.cgst = tax_res.cgst_amount
            existing_item.sgst = tax_res.sgst_amount
            existing_item.tax_amount = tax_res.total_tax
            existing_item.line_total = tax_res.line_total
        else:
            tax_res = calculate_product_line_item(product, qty)
            new_item = BillItem(
                bill_id=bill.id,
                product_id=product.id,
                product_name_snapshot=product.name,
                quantity=qty,
                unit_price=product.selling_price,
                cost_price=product.cost_price,
                mrp=product.mrp,
                gst_rate=product.gst_rate,
                hsn_code=product.hsn_code,
                taxable_amount=tax_res.taxable_amount,
                cgst=tax_res.cgst_amount,
                sgst=tax_res.sgst_amount,
                tax_amount=tax_res.total_tax,
                line_total=tax_res.line_total,
            )
            s.add(new_item)
            bill.items.append(new_item)

        _recalculate_bill_totals(bill)
        s.commit()
        s.refresh(bill)
        return bill_to_dto(bill)

    if db is not None and isinstance(db, Session):
        return _do_add(db)
    else:
        with get_db_context() as s:
            return _do_add(s)


def update_bill_item(
    db: Optional[Session | int] = None,
    bill_id: Optional[int] = None,
    item_id: Optional[int] = None,
    quantity: Optional[Decimal | float | str] = None,
) -> BillDTO:
    """
    Update quantity of a line item in a draft bill. Stock is NOT modified.
    """
    if not isinstance(db, Session):
        quantity = item_id
        item_id = bill_id
        bill_id = db
        db = None

    def _do_update(s: Session) -> BillDTO:
        try:
            qty = Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity
        except (ValueError, TypeError, InvalidOperation):
            raise InvalidQuantityError(f"Invalid quantity: {quantity}")

        if qty <= Decimal("0.00"):
            raise InvalidQuantityError("Quantity must be strictly greater than 0.")

        bill = s.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)
        if bill.status == "FINALIZED":
            raise BillAlreadyFinalizedError(bill_id)
        if bill.status != "DRAFT":
            raise BillNotDraftError(bill_id, bill.status)

        item = s.query(BillItem).filter(BillItem.id == item_id, BillItem.bill_id == bill_id).first()
        if not item:
            raise BillingError(f"Bill item with ID '{item_id}' not found in bill '{bill_id}'.")

        tax_res = calculate_line_item_gst(
            unit_price=item.unit_price,
            quantity=qty,
            gst_rate=item.gst_rate,
            hsn_code=item.hsn_code,
        )
        item.quantity = qty
        item.taxable_amount = tax_res.taxable_amount
        item.cgst = tax_res.cgst_amount
        item.sgst = tax_res.sgst_amount
        item.tax_amount = tax_res.total_tax
        item.line_total = tax_res.line_total

        _recalculate_bill_totals(bill)
        s.commit()
        s.refresh(bill)
        return bill_to_dto(bill)

    if db is not None and isinstance(db, Session):
        return _do_update(db)
    else:
        with get_db_context() as s:
            return _do_update(s)


def remove_bill_item(
    db: Optional[Session | int] = None,
    bill_id: Optional[int] = None,
    item_id: Optional[int] = None,
) -> BillDTO:
    """
    Remove line item from a draft bill. Stock is NOT modified.
    """
    if not isinstance(db, Session):
        item_id = bill_id
        bill_id = db
        db = None

    def _do_remove(s: Session) -> BillDTO:
        bill = s.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)
        if bill.status == "FINALIZED":
            raise BillAlreadyFinalizedError(bill_id)
        if bill.status != "DRAFT":
            raise BillNotDraftError(bill_id, bill.status)

        item = s.query(BillItem).filter(BillItem.id == item_id, BillItem.bill_id == bill_id).first()
        if not item:
            raise BillingError(f"Bill item with ID '{item_id}' not found in bill '{bill_id}'.")

        s.delete(item)
        s.flush()
        _recalculate_bill_totals(bill)
        s.commit()
        s.refresh(bill)
        return bill_to_dto(bill)

    if db is not None and isinstance(db, Session):
        return _do_remove(db)
    else:
        with get_db_context() as s:
            return _do_remove(s)


def calculate_bill(
    db: Optional[Session | int] = None,
    bill_id: Optional[int] = None,
) -> BillDTO:
    """
    Recalculate all totals for a bill using the GST engine.
    """
    if not isinstance(db, Session):
        if isinstance(db, int):
            bill_id = db
        db = None

    def _do_calc(s: Session) -> BillDTO:
        bill = s.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)

        for item in bill.items:
            tax_res = calculate_line_item_gst(
                unit_price=item.unit_price,
                quantity=item.quantity,
                gst_rate=item.gst_rate,
                hsn_code=item.hsn_code,
            )
            item.taxable_amount = tax_res.taxable_amount
            item.cgst = tax_res.cgst_amount
            item.sgst = tax_res.sgst_amount
            item.tax_amount = tax_res.total_tax
            item.line_total = tax_res.line_total

        _recalculate_bill_totals(bill)
        s.commit()
        s.refresh(bill)
        return bill_to_dto(bill)

    if db is not None and isinstance(db, Session):
        return _do_calc(db)
    else:
        with get_db_context() as s:
            return _do_calc(s)


@retry_on_lock()
def finalize_bill(
    db: Optional[Session | int] = None,
    bill_id: Optional[int] = None,
    payment_method: Optional[str] = None,
    payment_amount: Optional[Decimal] = None,
    idempotency_key: Optional[str] = None,
) -> BillDTO:
    """
    Atomically finalize draft bill.
    """
    if not isinstance(db, Session):
        if isinstance(db, (int, str)):
            idempotency_key = payment_method if payment_method != "CASH" else idempotency_key
            payment_method = bill_id if isinstance(bill_id, str) else payment_method
            bill_id = db
        db = None

    def _do_finalize(s: Session) -> BillDTO:
        bill = s.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)

        if bill.status == "FINALIZED":
            return bill_to_dto(bill)

        if bill.status != "DRAFT":
            raise BillNotDraftError(bill_id, bill.status)

        if not bill.items:
            raise EmptyBillError(bill_id)

        try:
            _recalculate_bill_totals(bill)

            for item in bill.items:
                product = s.query(Product).filter(Product.id == item.product_id).with_for_update().first()
                if not product:
                    raise ProductNotFoundError(item.product_id)
                if not product.active:
                    raise ProductInactiveError(item.product_id)
                if product.stock_quantity < item.quantity:
                    raise InsufficientStockError(
                        product_name=product.name,
                        requested=str(item.quantity),
                        available=str(product.stock_quantity),
                    )

            for item in bill.items:
                product = s.query(Product).filter(Product.id == item.product_id).with_for_update().first()
                new_stock = product.stock_quantity - item.quantity
                product.stock_quantity = new_stock

                movement = StockMovement(
                    product_id=product.id,
                    movement_type="SALE",
                    quantity=-item.quantity,
                    stock_after=new_stock,
                    reference_id=bill.bill_number,
                    notes=f"Sale in Bill #{bill.bill_number}",
                )
                s.add(movement)

            amount = payment_amount if payment_amount is not None else bill.grand_total
            method = payment_method if payment_method is not None else "CASH"

            from app.services.payment_service import process_payment
            process_payment(
                s,
                bill_id=bill.id,
                method=method,
                amount=amount,
                idempotency_key=idempotency_key,
            )

            bill.status = "FINALIZED"
            s.commit()
            s.refresh(bill)
            return bill_to_dto(bill)
        except Exception:
            s.rollback()
            raise

    if db is not None and isinstance(db, Session):
        return _do_finalize(db)
    else:
        with get_db_context() as s:
            return _do_finalize(s)

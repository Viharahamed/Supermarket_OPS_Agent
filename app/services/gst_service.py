from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

from app.db.models import Product
from app.exceptions import (
    InvalidPriceError,
    InvalidQuantityError,
    PriceBelowCostError,
    PriceAboveMRPError,
    InvalidGSTRateError,
)
from app.services.schemas import LineItemTaxResult

TWOPLACES = Decimal("0.01")


def quantize_money(amount: Decimal | float | str) -> Decimal:
    """
    Quantize monetary values to 2 decimal places using ROUND_HALF_UP policy consistently.
    """
    if not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError, InvalidOperation):
            raise InvalidPriceError(f"Invalid monetary value: {amount}")
    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def validate_pricing(
    cost_price: Decimal | float | str,
    selling_price: Decimal | float | str,
    mrp: Decimal | float | str,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Validate product pricing relationships:
    - Non-negative prices
    - Selling price >= cost price (reject below-cost selling)
    - Selling price <= MRP (reject selling above MRP)
    """
    try:
        cp = quantize_money(cost_price)
        sp = quantize_money(selling_price)
        mrp_val = quantize_money(mrp)
    except Exception as e:
        if isinstance(e, InvalidPriceError):
            raise
        raise InvalidPriceError(f"Invalid pricing inputs: {e}")

    if cp < Decimal("0.00"):
        raise InvalidPriceError("Cost price cannot be negative.")
    if sp < Decimal("0.00"):
        raise InvalidPriceError("Selling price cannot be negative.")
    if mrp_val < Decimal("0.00"):
        raise InvalidPriceError("MRP cannot be negative.")

    if sp < cp:
        raise PriceBelowCostError(selling_price=str(sp), cost_price=str(cp))
    if sp > mrp_val:
        raise PriceAboveMRPError(selling_price=str(sp), mrp=str(mrp_val))

    return cp, sp, mrp_val


def calculate_line_item_gst(
    unit_price: Decimal | float | str,
    quantity: Decimal | float | str,
    gst_rate: Decimal | float | str,
    hsn_code: Optional[str] = None,
) -> LineItemTaxResult:
    """
    Calculate deterministic intra-state GST (CGST + SGST), taxable amount, tax total, and line total.
    """
    try:
        price = quantize_money(unit_price)
    except Exception:
        raise InvalidPriceError(f"Invalid unit price: {unit_price}")

    try:
        if isinstance(quantity, Decimal):
            qty = quantity
        else:
            qty = Decimal(str(quantity))
    except (ValueError, TypeError, InvalidOperation):
        raise InvalidQuantityError(f"Invalid quantity: {quantity}")

    try:
        if isinstance(gst_rate, Decimal):
            rate = gst_rate
        else:
            rate = Decimal(str(gst_rate))
    except (ValueError, TypeError, InvalidOperation):
        raise InvalidGSTRateError(str(gst_rate))

    if price < Decimal("0.00"):
        raise InvalidPriceError("Unit price cannot be negative.")
    if qty <= Decimal("0.00"):
        raise InvalidQuantityError("Line item quantity must be strictly greater than 0.")
    if rate < Decimal("0.00"):
        raise InvalidGSTRateError(str(rate))

    # Calculate taxable amount
    taxable_amount = quantize_money(price * qty)

    # Intra-state GST equal split (CGST 50%, SGST 50%)
    cgst_rate = rate / Decimal("2")
    sgst_rate = rate / Decimal("2")

    cgst_amount = quantize_money(taxable_amount * (cgst_rate / Decimal("100")))
    sgst_amount = quantize_money(taxable_amount * (sgst_rate / Decimal("100")))

    total_tax = cgst_amount + sgst_amount
    line_total = taxable_amount + total_tax

    return LineItemTaxResult(
        unit_price=price,
        quantity=qty,
        taxable_amount=taxable_amount,
        gst_rate=rate,
        cgst_rate=cgst_rate,
        cgst_amount=cgst_amount,
        sgst_rate=sgst_rate,
        sgst_amount=sgst_amount,
        total_tax=total_tax,
        line_total=line_total,
        hsn_code=hsn_code,
    )


def calculate_product_line_item(
    product: Product,
    quantity: Decimal | float | str,
) -> LineItemTaxResult:
    """
    Helper function to calculate GST line item directly from a Product entity.
    """
    validate_pricing(
        cost_price=product.cost_price,
        selling_price=product.selling_price,
        mrp=product.mrp,
    )
    return calculate_line_item_gst(
        unit_price=product.selling_price,
        quantity=quantity,
        gst_rate=product.gst_rate,
        hsn_code=product.hsn_code,
    )

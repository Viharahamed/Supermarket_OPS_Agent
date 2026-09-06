from decimal import Decimal
import pytest

from app.db.models import Product
from app.exceptions import (
    InvalidPriceError,
    InvalidQuantityError,
    PriceBelowCostError,
    PriceAboveMRPError,
    InvalidGSTRateError,
)
from app.services import (
    quantize_money,
    validate_pricing,
    calculate_line_item_gst,
    calculate_product_line_item,
)


# 1. 0% GST calculation
def test_gst_0_percent():
    res = calculate_line_item_gst(
        unit_price=Decimal("100.00"),
        quantity=Decimal("1.00"),
        gst_rate=Decimal("0.00"),
        hsn_code="1101",
    )
    assert res.taxable_amount == Decimal("100.00")
    assert res.cgst_rate == Decimal("0.00")
    assert res.sgst_rate == Decimal("0.00")
    assert res.cgst_amount == Decimal("0.00")
    assert res.sgst_amount == Decimal("0.00")
    assert res.total_tax == Decimal("0.00")
    assert res.line_total == Decimal("100.00")
    assert res.hsn_code == "1101"


# 2. 5% GST calculation
def test_gst_5_percent():
    res = calculate_line_item_gst(
        unit_price=Decimal("100.00"),
        quantity=Decimal("2.00"),
        gst_rate=Decimal("5.00"),
    )
    assert res.taxable_amount == Decimal("200.00")
    assert res.cgst_rate == Decimal("2.50")
    assert res.sgst_rate == Decimal("2.50")
    assert res.cgst_amount == Decimal("5.00")
    assert res.sgst_amount == Decimal("5.00")
    assert res.total_tax == Decimal("10.00")
    assert res.line_total == Decimal("210.00")


# 3. 12% GST calculation
def test_gst_12_percent():
    res = calculate_line_item_gst(
        unit_price=Decimal("150.00"),
        quantity=Decimal("1.00"),
        gst_rate=Decimal("12.00"),
    )
    assert res.taxable_amount == Decimal("150.00")
    assert res.cgst_rate == Decimal("6.00")
    assert res.sgst_rate == Decimal("6.00")
    assert res.cgst_amount == Decimal("9.00")
    assert res.sgst_amount == Decimal("9.00")
    assert res.total_tax == Decimal("18.00")
    assert res.line_total == Decimal("168.00")


# 4. 18% GST calculation
def test_gst_18_percent():
    res = calculate_line_item_gst(
        unit_price=Decimal("200.00"),
        quantity=Decimal("1.00"),
        gst_rate=Decimal("18.00"),
    )
    assert res.taxable_amount == Decimal("200.00")
    assert res.cgst_rate == Decimal("9.00")
    assert res.sgst_rate == Decimal("9.00")
    assert res.cgst_amount == Decimal("18.00")
    assert res.sgst_amount == Decimal("18.00")
    assert res.total_tax == Decimal("36.00")
    assert res.line_total == Decimal("236.00")


# 5 & 6. CGST and SGST equal split validation
def test_cgst_sgst_split():
    rates = [Decimal("0.00"), Decimal("5.00"), Decimal("12.00"), Decimal("18.00")]
    for r in rates:
        res = calculate_line_item_gst(Decimal("100.00"), Decimal("1.00"), r)
        assert res.cgst_rate == r / Decimal("2")
        assert res.sgst_rate == r / Decimal("2")
        assert res.cgst_amount == res.sgst_amount


# 7, 8 & 9. Taxable amount, total tax, and final line total correctness
def test_line_item_breakdown_correctness():
    res = calculate_line_item_gst(
        unit_price=Decimal("45.50"),
        quantity=Decimal("3.00"),
        gst_rate=Decimal("12.00"),
    )
    expected_taxable = Decimal("136.50")  # 45.50 * 3
    expected_cgst = Decimal("8.19")       # 136.50 * 0.06 = 8.19
    expected_sgst = Decimal("8.19")
    expected_total_tax = Decimal("16.38")
    expected_line_total = Decimal("152.88")

    assert res.taxable_amount == expected_taxable
    assert res.cgst_amount == expected_cgst
    assert res.sgst_amount == expected_sgst
    assert res.total_tax == expected_total_tax
    assert res.line_total == expected_line_total


# 10 & 11. Exact Decimal precision and ROUND_HALF_UP quantization
def test_decimal_precision_and_rounding():
    # Unit price 33.33, Qty 1, GST 5%
    # Taxable = 33.33
    # CGST rate = 2.5% -> 33.33 * 0.025 = 0.83325 -> quantizes ROUND_HALF_UP to 0.83
    # SGST rate = 2.5% -> 0.83
    # Total tax = 1.66
    # Line total = 34.99
    res = calculate_line_item_gst(
        unit_price=Decimal("33.33"),
        quantity=Decimal("1.00"),
        gst_rate=Decimal("5.00"),
    )
    assert res.cgst_amount == Decimal("0.83")
    assert res.sgst_amount == Decimal("0.83")
    assert res.total_tax == Decimal("1.66")
    assert res.line_total == Decimal("34.99")

    # Rounding edge case: 33.30 * 0.025 = 0.8325 -> 0.83
    # 33.40 * 0.025 = 0.835 -> 0.84 (ROUND_HALF_UP)
    res_half_up = calculate_line_item_gst(
        unit_price=Decimal("33.40"),
        quantity=Decimal("1.00"),
        gst_rate=Decimal("5.00"),
    )
    assert res_half_up.cgst_amount == Decimal("0.84")


# 12. Zero quantity rejection
def test_zero_quantity_rejection():
    with pytest.raises(InvalidQuantityError):
        calculate_line_item_gst(Decimal("100.00"), Decimal("0.00"), Decimal("5.00"))

    with pytest.raises(InvalidQuantityError):
        calculate_line_item_gst(Decimal("100.00"), Decimal("-2.00"), Decimal("5.00"))


# 13. Negative price rejection
def test_negative_price_rejection():
    with pytest.raises(InvalidPriceError):
        calculate_line_item_gst(Decimal("-50.00"), Decimal("1.00"), Decimal("5.00"))

    with pytest.raises(InvalidPriceError):
        validate_pricing(cost_price=Decimal("-10.00"), selling_price=Decimal("20.00"), mrp=Decimal("20.00"))


# 14. Below-cost price rejection
def test_below_cost_price_rejection():
    with pytest.raises(PriceBelowCostError):
        validate_pricing(
            cost_price=Decimal("50.00"),
            selling_price=Decimal("45.00"),
            mrp=Decimal("55.00"),
        )


# 15. Selling price above MRP rejection
def test_selling_price_above_mrp_rejection():
    with pytest.raises(PriceAboveMRPError):
        validate_pricing(
            cost_price=Decimal("50.00"),
            selling_price=Decimal("65.00"),
            mrp=Decimal("60.00"),
        )


# 16. Missing/invalid GST rate
def test_invalid_gst_rate():
    with pytest.raises(InvalidGSTRateError):
        calculate_line_item_gst(Decimal("100.00"), Decimal("1.00"), Decimal("-5.00"))


# 17. Multiple integer quantities calculation
def test_multiple_integer_quantities():
    res = calculate_line_item_gst(
        unit_price=Decimal("120.00"),
        quantity=Decimal("10.00"),
        gst_rate=Decimal("18.00"),
    )
    assert res.taxable_amount == Decimal("1200.00")
    assert res.cgst_amount == Decimal("108.00")
    assert res.sgst_amount == Decimal("108.00")
    assert res.total_tax == Decimal("216.00")
    assert res.line_total == Decimal("1416.00")


# 18. Fractional quantities calculation (e.g., loose items like 1.5 kg)
def test_fractional_quantities():
    # 1.5 kg @ 245.50 per kg with 5% GST
    # Taxable = 1.5 * 245.50 = 368.25
    # CGST 2.5% = 368.25 * 0.025 = 9.20625 -> 9.21
    # SGST 2.5% = 9.21
    # Total tax = 18.42
    # Line total = 386.67
    res = calculate_line_item_gst(
        unit_price=Decimal("245.50"),
        quantity=Decimal("1.50"),
        gst_rate=Decimal("5.00"),
    )
    assert res.taxable_amount == Decimal("368.25")
    assert res.cgst_amount == Decimal("9.21")
    assert res.sgst_amount == Decimal("9.21")
    assert res.total_tax == Decimal("18.42")
    assert res.line_total == Decimal("386.67")


# Test product-level calculation helper
def test_calculate_product_line_item():
    product = Product(
        sku="OIL-FORT-1L",
        name="Fortune Sunflower Oil 1L",
        cost_price=Decimal("110.00"),
        selling_price=Decimal("135.00"),
        mrp=Decimal("145.00"),
        gst_rate=Decimal("5.00"),
        hsn_code="1512",
    )
    res = calculate_product_line_item(product, Decimal("2.00"))
    assert res.unit_price == Decimal("135.00")
    assert res.taxable_amount == Decimal("270.00")
    assert res.cgst_amount == Decimal("6.75")
    assert res.sgst_amount == Decimal("6.75")
    assert res.total_tax == Decimal("13.50")
    assert res.line_total == Decimal("283.50")
    assert res.hsn_code == "1512"

from decimal import Decimal
from enum import Enum
from datetime import datetime
from typing import Optional, List, Tuple
from pydantic import BaseModel, ConfigDict


class StockStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class ProductDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    sku: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    unit: str
    pack_size: Decimal
    is_loose: bool
    cost_price: Decimal
    selling_price: Decimal
    mrp: Decimal
    gst_rate: Decimal
    hsn_code: Optional[str] = None
    stock_quantity: Decimal
    reorder_level: Decimal
    active: bool


class StockStatusDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    sku: str
    stock_quantity: Decimal
    unit: str
    reorder_level: Decimal
    stock_status: StockStatus
    product: ProductDTO


class StockMovementDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    movement_type: str
    quantity: Decimal
    stock_after: Decimal
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class LineItemTaxResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_price: Decimal
    quantity: Decimal
    taxable_amount: Decimal
    gst_rate: Decimal
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    total_tax: Decimal
    line_total: Decimal
    hsn_code: Optional[str] = None


class BillItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_id: int
    product_id: int
    product_name_snapshot: str
    quantity: Decimal
    unit_price: Decimal
    cost_price: Decimal
    mrp: Decimal
    gst_rate: Decimal
    hsn_code: Optional[str] = None
    taxable_amount: Decimal
    cgst: Decimal
    sgst: Decimal
    tax_amount: Decimal
    line_total: Decimal
    created_at: datetime


class BillDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_number: str
    idempotency_key: Optional[str] = None
    status: str
    customer_id: Optional[int] = None
    payment_method: str
    payment_status: str
    subtotal: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    tax_total: Decimal
    discount_amount: Decimal
    rounding_amount: Decimal
    grand_total: Decimal
    items: List[BillItemDTO] = []
    created_at: datetime
    updated_at: datetime

class PaymentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bill_id: int
    method: str
    amount: Decimal
    split_components: Optional[List[Tuple[str, Decimal]]] = None
    idempotency_key: Optional[str] = None

# ------------------------------------------------------------
# Reporting DTOs
# ------------------------------------------------------------

class Period(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    start: str  # ISO date string
    end: str    # ISO date string

class DailySalesReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: Period
    bill_count: int
    subtotal: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    tax_total: Decimal
    rounding_amount: Decimal
    grand_total: Decimal

class SalesSummaryReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: Period
    total_bills: int
    total_taxable_amount: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_tax: Decimal
    total_sales: Decimal
    average_bill_value: Decimal
    highest_bill_value: Decimal
    lowest_bill_value: Decimal

class PaymentBreakdownReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: Period
    cash: Decimal
    upi: Decimal
    card: Decimal
    khata: Decimal
    total: Decimal
    inconsistency: Optional[str] = None

class TopProductDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    quantity_sold: Decimal
    sales_value: Decimal

class GstSlab(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gst_rate: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    total_gst: Decimal

class GstSummaryReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: Period
    total_taxable_amount: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_gst: Decimal
    slabs: List[GstSlab] = []

class ReorderCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    current_quantity: Decimal
    reorder_level: Decimal
    unit: str
    shortage_amount: Decimal

class StockHealthReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    in_stock: List[StockStatusDTO] = []
    low_stock: List[StockStatusDTO] = []
    out_of_stock: List[StockStatusDTO] = []
    reorder_candidates: List[ReorderCandidate] = []

class DailyCloseReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: Period
    daily_sales: DailySalesReport
    sales_summary: SalesSummaryReport
    payment_breakdown: PaymentBreakdownReport
    top_products: List[TopProductDTO] = []
    stock_health: StockHealthReport

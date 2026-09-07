"""Tool layer input and output schemas.

All tool input models are Pydantic ``BaseModel`` classes that strictly type the arguments
expected by each tool.  The output format for every tool is a ``ToolResult`` model that
conforms to the required ``{ success, data, error }`` JSON shape.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Generic response / error models
# ---------------------------------------------------------------------------

class ToolError(BaseModel):
    """Structured error returned by a tool.

    ``code`` is a short machine‑readable identifier (e.g. ``INSUFFICIENT_STOCK``)
    and ``message`` is a human‑readable description.
    """

    code: str
    message: str

    model_config = ConfigDict(from_attributes=True)


class ToolResult(BaseModel):
    """Standardised result for all tools.

    ``success`` indicates whether the call succeeded. ``data`` contains the payload
    when ``success`` is ``True``; otherwise ``error`` contains a ``ToolError``.
    """

    success: bool
    data: Optional[Any] = None
    error: Optional[ToolError] = None

    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Inventory tool input models
# ---------------------------------------------------------------------------

class SearchProductsInput(BaseModel):
    query: str = Field(..., description="Search query for product name, SKU, etc.")
    active_only: bool = Field(
        default=True,
        description="Whether to limit results to active products.",
    )

    model_config = ConfigDict(extra="forbid")


class GetStockInput(BaseModel):
    product_id: int = Field(..., description="Database identifier of the product.")

    model_config = ConfigDict(extra="forbid")


class ReceiveStockInput(BaseModel):
    product_id: int
    quantity: Decimal
    cost_price: Decimal
    mrp: Decimal
    reference: Optional[str] = None
    notes: Optional[str] = None
    query_phrase: Optional[str] = Field(None, description="Exact search query phrase used to search for and resolve this product.")

    @field_validator("quantity", "cost_price", "mrp")
    @classmethod
    def positive_decimal(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("must be > 0")
        return v

    model_config = ConfigDict(extra="forbid")


class AdjustStockInput(BaseModel):
    product_id: int
    quantity_change: Decimal
    reason: str
    reference: Optional[str] = None
    query_phrase: Optional[str] = Field(None, description="Exact search query phrase used to search for and resolve this product.")

    @field_validator("quantity_change")
    @classmethod
    def nonzero(cls, v: Decimal) -> Decimal:
        if v == Decimal("0"):
            raise ValueError("quantity_change cannot be zero")
        return v

    @field_validator("reason")
    @classmethod
    def nonempty_reason(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason must be non‑empty")
        return v

    model_config = ConfigDict(extra="forbid")


class GetLowStockInput(BaseModel):
    # No arguments required – placeholder for future filters.
    pass

    model_config = ConfigDict(extra="forbid")

# ---------------------------------------------------------------------------
# Billing tool input models
# ---------------------------------------------------------------------------

class CreateDraftBillInput(BaseModel):
    customer_id: Optional[int] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class GetCurrentBillInput(BaseModel):
    bill_id: int

    model_config = ConfigDict(extra="forbid")


class AddBillItemInput(BaseModel):
    bill_id: int
    product_id: int
    quantity: Decimal
    query_phrase: Optional[str] = Field(None, description="Exact search query phrase used to search for and resolve this product.")

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("quantity must be > 0")
        return v

    model_config = ConfigDict(extra="forbid")


class BatchBillItemInput(BaseModel):
    product_id: int = Field(..., description="Database product ID to add")
    quantity: Decimal = Field(..., description="Quantity to add (must be > 0)")
    query_phrase: Optional[str] = Field(None, description="Exact search query phrase used to search for and resolve this product.")

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("quantity must be > 0")
        return v

    model_config = ConfigDict(extra="forbid")



class AddBillItemsInput(BaseModel):
    bill_id: int = Field(..., description="Target draft bill ID")
    items: List[BatchBillItemInput] = Field(..., description="List of product items and quantities to add in a single batch")

    model_config = ConfigDict(extra="forbid")


class UpdateBillItemInput(BaseModel):
    bill_id: int
    item_id: int
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("quantity must be > 0")
        return v

    model_config = ConfigDict(extra="forbid")


class RemoveBillItemInput(BaseModel):
    bill_id: int
    item_id: int

    model_config = ConfigDict(extra="forbid")


class CalculateBillInput(BaseModel):
    bill_id: int

    model_config = ConfigDict(extra="forbid")


class FinalizeBillInput(BaseModel):
    bill_id: int
    payment_method: Optional[str] = None
    payment_amount: Optional[Decimal] = None
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

# ---------------------------------------------------------------------------
# Khata tool input models
# ---------------------------------------------------------------------------

class FindCustomerInput(BaseModel):
    query: str

    model_config = ConfigDict(extra="forbid")


class CreateCustomerInput(BaseModel):
    name: str
    phone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must be non‑empty")
        return v

    model_config = ConfigDict(extra="forbid")


class AddCreditInput(BaseModel):
    customer_id: int
    amount: Decimal
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("amount must be > 0")
        return v

    model_config = ConfigDict(extra="forbid")


class RecordPaymentInput(BaseModel):
    customer_id: int
    amount: Decimal
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("amount must be > 0")
        return v

    model_config = ConfigDict(extra="forbid")


class GetKhataBalanceInput(BaseModel):
    customer_id: int

    model_config = ConfigDict(extra="forbid")


class GetKhataHistoryInput(BaseModel):
    customer_id: int
    limit: Optional[int] = None

    model_config = ConfigDict(extra="forbid")

# ---------------------------------------------------------------------------
# Reporting tool input models
# ---------------------------------------------------------------------------

class DateRangeInput(BaseModel):
    start: str  # ISO date string
    end: str    # ISO date string

    model_config = ConfigDict(extra="forbid")


class GetDailySalesInput(BaseModel):
    report_date: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class GetSalesSummaryInput(DateRangeInput):
    pass


class GetPaymentBreakdownInput(DateRangeInput):
    pass


class GetTopProductsInput(DateRangeInput):
    limit: Optional[int] = None
    by: Optional[str] = "quantity"


class GetGstSummaryInput(DateRangeInput):
    pass


class GetDailyCloseInput(BaseModel):
    report_date: Optional[str] = Field(default=None, description="ISO date for the daily close report (defaults to today if omitted)")

    model_config = ConfigDict(extra="forbid")


class GetStockHealthInput(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

# ---------------------------------------------------------------------------
# Preference tool input models
# ---------------------------------------------------------------------------

class GetPreferenceInput(BaseModel):
    key: str

    model_config = ConfigDict(extra="forbid")


class SetPreferenceInput(BaseModel):
    key: str
    value: Any

    model_config = ConfigDict(extra="forbid")


class ListPreferencesInput(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")


# Aliases for preference inputs to match different naming conventions
GetUserPreferencesInput = GetPreferenceInput
UpdateUserPreferencesInput = SetPreferenceInput


# ---------------------------------------------------------------------------
# Document Generation Tool input models
# ---------------------------------------------------------------------------

class GenerateInvoicePDFInput(BaseModel):
    bill_id: Optional[int] = Field(None, description="Integer Bill ID (e.g. 1, 1001)")
    bill_number: Optional[str] = Field(None, description="String Bill Number (e.g. BILL-20260906-XXXX)")

    model_config = ConfigDict(extra="forbid")


class GenerateSalesAnalysisPPTXInput(BaseModel):
    start_date: Optional[str] = Field(None, description="Start date YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="End date YYYY-MM-DD")
    days: Optional[int] = Field(7, description="Trailing number of days if start_date is omitted")

    model_config = ConfigDict(extra="forbid")


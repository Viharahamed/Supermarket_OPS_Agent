# app/tools/registry.py
"""Tool registry for Kirana AI Agent.

The registry holds a mapping of tool names to their definitions. Each definition
contains a human‑readable description, the Pydantic input schema class, and a
callable handler that implements the tool logic.

The registry exposes a tiny API used by the agent harness:

- ``register(name, description, schema, handler)`` – add a tool.
- ``get(name)`` – retrieve a definition or raise ``KeyError``.
- ``list_tools()`` – return a list of all registered tool names.
- ``execute(name, raw_args)`` – validate ``raw_args`` against the schema,
  invoke the handler, and return a ``ToolResult`` instance.

All errors are transformed into the ``ToolResult`` error shape so the LLM
receives a predictable JSON structure.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from pydantic import ValidationError

from app.tools.result import ToolResult, ToolError
from app.tools.schemas import (
    SearchProductsInput,
    GetStockInput,
    ReceiveStockInput,
    AdjustStockInput,
    GetLowStockInput,
    CreateDraftBillInput,
    GetCurrentBillInput,
    AddBillItemInput,
    AddBillItemsInput,
    UpdateBillItemInput,
    RemoveBillItemInput,
    CalculateBillInput,
    FinalizeBillInput,
    FindCustomerInput,
    CreateCustomerInput,
    AddCreditInput,
    RecordPaymentInput,
    GetKhataBalanceInput,
    GetKhataHistoryInput,
    DateRangeInput,
    GetDailySalesInput,
    GetSalesSummaryInput,
    GetPaymentBreakdownInput,
    GetTopProductsInput,
    GetGstSummaryInput,
    GetStockHealthInput,
    GetDailyCloseInput,
    GetPreferenceInput,
    SetPreferenceInput,
    ListPreferencesInput,
    GenerateInvoicePDFInput,
    GenerateSalesAnalysisPPTXInput,
)


class ToolDefinition:
    """Container for a single tool.

    Attributes
    ----------
    name: str – the tool identifier used by the LLM.
    description: str – a short, user‑friendly description.
    input_schema: type – a Pydantic ``BaseModel`` subclass.
    handler: Callable[[Any], Any] – function that receives a validated schema
        instance and returns the business data (or raises a known exception).
    """

    def __init__(self, name: str, description: str, input_schema: type, handler: Callable[[Any], Any]) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler

    def to_dict(self) -> Dict[str, Any]:
        schema_dict = (
            self.input_schema.model_json_schema()
            if hasattr(self.input_schema, "model_json_schema")
            else self.input_schema.schema()
        )
        return {"name": self.name, "description": self.description, "input_schema": schema_dict}


class ToolRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, input_schema: type, handler: Callable[[Any], Any]) -> None:
        if name in self._registry:
            raise ValueError(f"Tool '{name}' is already registered")
        self._registry[name] = ToolDefinition(name, description, input_schema, handler)

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._registry[name]
        except KeyError:
            raise KeyError(f"UNKNOWN_TOOL: {name}")

    def list_tools(self) -> List[Dict[str, Any]]:
        return [td.to_dict() for td in self._registry.values()]

    def execute(self, name: str, raw_args: dict, context: Any = None) -> ToolResult:
        """Validate arguments and run the handler with optional trusted execution context.

        Returns a ``ToolResult`` with ``success`` flag, ``data`` payload, and a
        ``ToolError`` when validation or business exceptions occur.
        """
        try:
            definition = self.get(name)
        except KeyError as exc:
            return ToolResult(success=False, error=ToolError(code="UNKNOWN_TOOL", message=str(exc)))
        try:
            validated = definition.input_schema(**raw_args)
        except ValidationError as ve:
            return ToolResult(
                success=False,
                error=ToolError(
                    code="INVALID_TOOL_ARGUMENTS",
                    message=ve.errors()[0]["msg"] if ve.errors() else "Invalid arguments",
                ),
            )

        try:
            import inspect
            sig = inspect.signature(definition.handler)
            if context is not None and ("context" in sig.parameters or len(sig.parameters) >= 2):
                result = definition.handler(validated, context=context)
            else:
                result = definition.handler(validated)
            return ToolResult(success=True, data=result)
        except Exception as exc:
            return ToolResult(success=False, error=ToolError(code="TOOL_EXECUTION_ERROR", message=str(exc)))


# Global singleton used by the application
registry = ToolRegistry()

# ---------------------------------------------------------------------------
# Register all tools
# ---------------------------------------------------------------------------
from app.tools.inventory import search_products, get_stock, receive_stock, adjust_stock, get_low_stock
from app.tools.billing import (
    create_draft_bill,
    get_current_bill,
    add_bill_item,
    add_bill_items,
    update_bill_item,
    remove_bill_item,
    calculate_bill,
    finalize_bill,
)
from app.tools.khata import (
    find_customer,
    create_customer,
    add_credit,
    record_payment,
    get_khata_balance,
    get_khata_history,
)
from app.tools.reporting import get_daily_sales, get_monthly_sales, get_product_performance, get_daily_close
from app.tools.preferences import get_user_preferences, update_user_preferences
from app.tools.documents import generate_invoice_pdf, generate_sales_analysis_pptx

# Inventory tools
registry.register("search_products", "Search products by name, SKU, or category.", SearchProductsInput, search_products)
registry.register("get_stock", "Retrieve current stock information for a product.", GetStockInput, get_stock)
registry.register("receive_stock", "Increase stock for a product and record a STOCK_IN movement.", ReceiveStockInput, receive_stock)
registry.register("adjust_stock", "Adjust stock up or down with an audit reason.", AdjustStockInput, adjust_stock)
registry.register("get_low_stock", "List all products with low or out‑of‑stock levels.", GetLowStockInput, get_low_stock)

# Billing tools
registry.register("create_draft_bill", "Create a new draft bill (optional customer).", CreateDraftBillInput, create_draft_bill)
registry.register("get_current_bill", "Fetch a bill by its identifier.", GetCurrentBillInput, get_current_bill)
registry.register("add_bill_item", "Add a single product line item to a draft bill.", AddBillItemInput, add_bill_item)
registry.register("add_bill_items", "Add multiple product line items to a draft bill in a single batch operation.", AddBillItemsInput, add_bill_items)
registry.register("update_bill_item", "Change the quantity of an existing bill line item.", UpdateBillItemInput, update_bill_item)
registry.register("remove_bill_item", "Remove a line item from a draft bill.", RemoveBillItemInput, remove_bill_item)
registry.register("calculate_bill", "Re‑calculate totals for a bill (useful after manual edits).", CalculateBillInput, calculate_bill)
registry.register("finalize_bill", "Finalize a draft bill, decrement stock and record a SALE.", FinalizeBillInput, finalize_bill)

# Khata tools
registry.register("find_customer", "Lookup a customer by name, phone or email.", FindCustomerInput, find_customer)
registry.register("create_customer", "Create a new customer record.", CreateCustomerInput, create_customer)
registry.register("add_credit", "Add a credit transaction to a customer's khata.", AddCreditInput, add_credit)
registry.register("record_payment", "Record a payment against a customer's khata.", RecordPaymentInput, record_payment)
registry.register("get_khata_balance", "Retrieve the current balance for a customer.", GetKhataBalanceInput, get_khata_balance)
registry.register("get_khata_history", "Fetch recent credit/payment history for a customer.", GetKhataHistoryInput, get_khata_history)

# Reporting tools
registry.register("get_daily_sales", "Return total sales for a specific date range.", GetDailySalesInput, get_daily_sales)
registry.register("get_monthly_sales", "Return total sales for a month.", GetSalesSummaryInput, get_monthly_sales)
registry.register("get_product_performance", "Return sales performance for a product over a date range.", GetTopProductsInput, get_product_performance)
registry.register("get_daily_close", "Generate a comprehensive end-of-day sales, tax, payment breakdown, and stock health report.", GetDailyCloseInput, get_daily_close)

# Preference tools
registry.register("get_user_preferences", "Fetch stored UI/behavior preferences for a user.", GetPreferenceInput, get_user_preferences)
registry.register("update_user_preferences", "Persist updated preferences for a user.", SetPreferenceInput, update_user_preferences)

# Document tools
registry.register("generate_invoice_pdf", "Generate a PDF tax invoice for a finalized bill.", GenerateInvoicePDFInput, generate_invoice_pdf)
registry.register("generate_sales_analysis_pptx", "Generate an 8-slide PowerPoint presentation analyzing sales performance.", GenerateSalesAnalysisPPTXInput, generate_sales_analysis_pptx)


# Module-level convenience functions delegating to singleton registry instance
def register(name: str, description: str, input_schema: type, handler: Callable[[Any], Any]) -> None:
    registry.register(name, description, input_schema, handler)


def get(name: str) -> ToolDefinition:
    return registry.get(name)


def list_tools() -> List[Dict[str, Any]]:
    return registry.list_tools()


def execute(name: str, raw_args: dict, context: Any = None) -> ToolResult:
    return registry.execute(name, raw_args, context=context)

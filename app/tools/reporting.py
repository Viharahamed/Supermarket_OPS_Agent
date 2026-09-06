# app/tools/reporting.py
"""Tool handlers for reporting actions.

These functions delegate to the existing reporting_service functions and return
plain dictionaries suitable for the ToolResult wrapper.
"""

from datetime import date

from app.services.reporting_service import (
    get_daily_sales as svc_get_daily_sales,
    get_sales_summary as svc_get_sales_summary,
    get_payment_breakdown as svc_get_payment_breakdown,
    get_top_products as svc_get_top_products,
    get_gst_summary as svc_get_gst_summary,
    get_stock_health as svc_get_stock_health,
    daily_close as svc_daily_close,
)
from app.tools.schemas import (
    GetDailySalesInput,
    GetSalesSummaryInput,
    GetPaymentBreakdownInput,
    GetTopProductsInput,
    GetGstSummaryInput,
    GetStockHealthInput,
    GetDailyCloseInput,
)


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def get_daily_sales(inp: GetDailySalesInput) -> dict:
    raw_date = inp.report_date or inp.start or date.today().isoformat()
    d = date.fromisoformat(raw_date)
    result = svc_get_daily_sales(d)
    return _to_dict(result)


def get_monthly_sales(inp: GetSalesSummaryInput) -> dict:
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_sales_summary(start_d, end_d)
    return _to_dict(result)


def get_product_performance(inp: GetTopProductsInput) -> list[dict]:
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    limit = inp.limit or 10
    by = inp.by or "quantity"
    result = svc_get_top_products(start_d, end_d, limit=limit, by=by)
    return [_to_dict(r) for r in result]


def get_sales_summary(inp: GetSalesSummaryInput) -> dict:
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_sales_summary(start_d, end_d)
    return _to_dict(result)


def get_payment_breakdown(inp: GetPaymentBreakdownInput) -> dict:
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_payment_breakdown(start_d, end_d)
    return _to_dict(result)


def get_top_products(inp: GetTopProductsInput) -> list[dict]:
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    limit = inp.limit or 10
    by = inp.by or "quantity"
    result = svc_get_top_products(start_d, end_d, limit=limit, by=by)
    return [_to_dict(r) for r in result]


def get_gst_summary(inp: GetGstSummaryInput) -> dict:
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_gst_summary(start_d, end_d)
    return _to_dict(result)


def get_stock_health(inp: GetStockHealthInput) -> dict:
    result = svc_get_stock_health()
    return _to_dict(result)


def get_daily_close(inp: GetDailyCloseInput) -> dict:
    d = date.fromisoformat(inp.report_date)
    result = svc_daily_close(d)
    return _to_dict(result)

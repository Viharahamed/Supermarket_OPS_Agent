# app/tools/reporting.py
"""Tool handlers for reporting actions with store_id context."""

from datetime import date
from typing import Any, Optional

from app.services.reporting_service import (
    get_store_date,
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


def _extract_store_id(context: Optional[Any]) -> int:
    if context and hasattr(context, "principal") and context.principal:
        return context.principal.store_id
    return 1


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def get_daily_sales(inp: GetDailySalesInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    raw_date = inp.report_date or inp.start or get_store_date().isoformat()
    d = date.fromisoformat(raw_date)
    result = svc_get_daily_sales(d, store_id=store_id)
    return _to_dict(result)


def get_monthly_sales(inp: GetSalesSummaryInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_sales_summary(start_d, end_d, store_id=store_id)
    return _to_dict(result)


def get_product_performance(inp: GetTopProductsInput, context: Optional[Any] = None) -> list[dict]:
    store_id = _extract_store_id(context)
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    limit = inp.limit or 10
    by = inp.by or "quantity"
    result = svc_get_top_products(start_d, end_d, limit=limit, by=by, store_id=store_id)
    return [_to_dict(r) for r in result]


def get_sales_summary(inp: GetSalesSummaryInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_sales_summary(start_d, end_d, store_id=store_id)
    return _to_dict(result)


def get_payment_breakdown(inp: GetPaymentBreakdownInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_payment_breakdown(start_d, end_d, store_id=store_id)
    return _to_dict(result)


def get_top_products(inp: GetTopProductsInput, context: Optional[Any] = None) -> list[dict]:
    store_id = _extract_store_id(context)
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    limit = inp.limit or 10
    by = inp.by or "quantity"
    result = svc_get_top_products(start_d, end_d, limit=limit, by=by, store_id=store_id)
    return [_to_dict(r) for r in result]


def get_gst_summary(inp: GetGstSummaryInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    start_d = date.fromisoformat(inp.start)
    end_d = date.fromisoformat(inp.end)
    result = svc_get_gst_summary(start_d, end_d, store_id=store_id)
    return _to_dict(result)


def get_stock_health(inp: GetStockHealthInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    result = svc_get_stock_health(store_id=store_id)
    return _to_dict(result)


def get_daily_close(inp: GetDailyCloseInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    d = date.fromisoformat(inp.report_date)
    result = svc_daily_close(d, store_id=store_id)
    return _to_dict(result)

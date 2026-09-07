# app/tools/inventory.py
"""Tool handlers for inventory-related actions.

Each function accepts a validated Pydantic input model from ``app.tools.schemas``
and optional trusted execution context, calling the inventory service.
"""

from typing import Any, Optional
from app.db.database import get_db_context
from app.services.inventory_service import (
    search_products as svc_search,
    get_stock as svc_get_stock,
    get_low_stock as svc_low_stock,
    receive_stock as svc_receive_stock,
    adjust_stock as svc_adjust_stock,
)
from app.tools.schemas import (
    SearchProductsInput,
    GetStockInput,
    ReceiveStockInput,
    AdjustStockInput,
    GetLowStockInput,
)


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return dict(obj)


def _extract_store_id(context: Optional[Any]) -> int:
    if context and hasattr(context, "principal") and context.principal:
        return context.principal.store_id
    return 1


def search_products(inp: SearchProductsInput, context: Optional[Any] = None) -> list[dict]:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        products = svc_search(db, inp.query, store_id=store_id, include_inactive=not inp.active_only)
        return [_to_dict(p) for p in products]


def get_stock(inp: GetStockInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        stock = svc_get_stock(db, inp.product_id, store_id=store_id)
        return _to_dict(stock)


def get_low_stock(inp: GetLowStockInput, context: Optional[Any] = None) -> list[dict]:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        low = svc_low_stock(db, store_id=store_id)
        return [_to_dict(p) for p in low]


def receive_stock(inp: ReceiveStockInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        movement = svc_receive_stock(
            db,
            inp.product_id,
            inp.quantity,
            inp.cost_price,
            inp.mrp,
            store_id=store_id,
            reference=inp.reference,
            notes=inp.notes,
        )
        return _to_dict(movement)


def adjust_stock(inp: AdjustStockInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        movement = svc_adjust_stock(
            db,
            inp.product_id,
            inp.quantity_change,
            inp.reason,
            store_id=store_id,
            reference=inp.reference,
        )
        return _to_dict(movement)

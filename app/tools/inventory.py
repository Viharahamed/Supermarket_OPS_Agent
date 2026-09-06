# app/tools/inventory.py
"""Tool handlers for inventory‑related actions.

Each function accepts a validated Pydantic input model from ``app.tools.schemas``
and calls the appropriate inventory service function.
"""

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


def search_products(inp: SearchProductsInput) -> list[dict]:
    with get_db_context() as db:
        products = svc_search(db, inp.query, include_inactive=not inp.active_only)
        return [_to_dict(p) for p in products]


def get_stock(inp: GetStockInput) -> dict:
    with get_db_context() as db:
        stock = svc_get_stock(db, inp.product_id)
        return _to_dict(stock)


def get_low_stock(inp: GetLowStockInput) -> list[dict]:
    with get_db_context() as db:
        low = svc_low_stock(db)
        return [_to_dict(p) for p in low]


def receive_stock(inp: ReceiveStockInput) -> dict:
    with get_db_context() as db:
        movement = svc_receive_stock(
            db,
            inp.product_id,
            inp.quantity,
            inp.cost_price,
            inp.mrp,
            reference=inp.reference,
            notes=inp.notes,
        )
        return _to_dict(movement)


def adjust_stock(inp: AdjustStockInput) -> dict:
    with get_db_context() as db:
        movement = svc_adjust_stock(
            db,
            inp.product_id,
            inp.quantity_change,
            inp.reason,
            reference=inp.reference,
        )
        return _to_dict(movement)

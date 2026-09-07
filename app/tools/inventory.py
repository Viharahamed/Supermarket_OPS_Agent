# app/tools/inventory.py
"""Tool handlers for inventory-related actions.

Each function accepts a validated Pydantic input model from ``app.tools.schemas``
and optional trusted execution context, calling the inventory service.
"""

from typing import Any, Optional
from app.db.database import get_db_context
from app.exceptions import ProductNotGroundedError
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


def normalize_text(text: Optional[str]) -> str:
    """Normalize text: convert to lowercase, strip, collapse repeated whitespace."""
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def _validate_product_grounding(product_id: int, query_phrase: Optional[str], context: Optional[Any]) -> None:
    if context is None:
        raise ProductNotGroundedError(product_id)

    p_id = int(product_id)

    if not hasattr(context, "grounded_product_ids") or context.grounded_product_ids is None or p_id not in context.grounded_product_ids:
        raise ProductNotGroundedError(product_id)
    if not hasattr(context, "grounded_product_queries") or context.grounded_product_queries is None:
        raise ProductNotGroundedError(product_id)

    valid_queries = context.grounded_product_queries.get(p_id)
    if not valid_queries:
        raise ProductNotGroundedError(product_id)

    if not query_phrase or not str(query_phrase).strip():
        raise ProductNotGroundedError(product_id)

    norm_q = normalize_text(query_phrase)

    # Layer 2: Exact query match against search queries that returned this product
    if norm_q not in valid_queries:
        raise ProductNotGroundedError(product_id)

    # Layer 3: Contiguous phrase match against original user message
    if hasattr(context, "user_message") and context.user_message:
        norm_user_msg = normalize_text(context.user_message)
        if norm_user_msg and norm_q not in norm_user_msg:
            raise ProductNotGroundedError(product_id)


def search_products(inp: SearchProductsInput, context: Optional[Any] = None) -> list[dict]:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        products = svc_search(db, inp.query, store_id=store_id, include_inactive=not inp.active_only)
        result_dicts = [_to_dict(p) for p in products]

        if context is not None:
            if not hasattr(context, "grounded_product_ids") or context.grounded_product_ids is None:
                context.grounded_product_ids = set()
            if not hasattr(context, "grounded_product_queries") or context.grounded_product_queries is None:
                context.grounded_product_queries = {}

            norm_query = normalize_text(inp.query)
            for p in products:
                p_id = getattr(p, "product_id", None) or getattr(p, "id", None)
                if p_id is None and isinstance(p, dict):
                    p_id = p.get("product_id") or p.get("id")
                if p_id is not None:
                    p_id_int = int(p_id)
                    context.grounded_product_ids.add(p_id_int)
                    if p_id_int not in context.grounded_product_queries:
                        context.grounded_product_queries[p_id_int] = set()
                    context.grounded_product_queries[p_id_int].add(norm_query)

        return result_dicts



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
    _validate_product_grounding(inp.product_id, getattr(inp, "query_phrase", None), context)
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
    _validate_product_grounding(inp.product_id, getattr(inp, "query_phrase", None), context)
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

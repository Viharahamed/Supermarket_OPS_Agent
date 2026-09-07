# app/tools/billing.py
"""Tool handlers for billing-related actions.

Each function accepts the validated Pydantic input model from
``app.tools.schemas`` and optional trusted execution context.
"""

from typing import Any, Optional
import uuid

from app.exceptions import ProductNotGroundedError
from app.tools.inventory import _validate_product_grounding
from app.services.billing_service import (
    create_draft_bill as svc_create_draft_bill,
    get_current_bill as svc_get_current_bill,
    add_bill_item as svc_add_bill_item,
    add_bill_items as svc_add_bill_items,
    update_bill_item as svc_update_bill_item,
    remove_bill_item as svc_remove_bill_item,
    calculate_bill as svc_calculate_bill,
    finalize_bill as svc_finalize_bill,
)
from app.db.database import get_db_context
from app.tools.schemas import (
    CreateDraftBillInput,
    GetCurrentBillInput,
    AddBillItemInput,
    AddBillItemsInput,
    UpdateBillItemInput,
    RemoveBillItemInput,
    CalculateBillInput,
    FinalizeBillInput,
)


def _extract_store_id(context: Optional[Any]) -> int:
    if context and hasattr(context, "principal") and context.principal:
        return context.principal.store_id
    return 1


def create_draft_bill(inp: CreateDraftBillInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    idem_key = inp.idempotency_key or f"draft_{uuid.uuid4().hex}"
    with get_db_context() as db:
        result = svc_create_draft_bill(
            db,
            customer_id=inp.customer_id,
            store_id=store_id,
            idempotency_key=idem_key,
        )
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def get_current_bill(inp: GetCurrentBillInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        result = svc_get_current_bill(db, inp.bill_id, store_id=store_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def add_bill_item(inp: AddBillItemInput, context: Optional[Any] = None) -> dict:
    _validate_product_grounding(inp.product_id, getattr(inp, "query_phrase", None), context)
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        result = svc_add_bill_item(db, inp.bill_id, inp.product_id, inp.quantity, store_id=store_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def add_bill_items(inp: AddBillItemsInput, context: Optional[Any] = None) -> dict:
    for item in inp.items:
        _validate_product_grounding(item.product_id, getattr(item, "query_phrase", None), context)
    store_id = _extract_store_id(context)
    items_list = [{"product_id": item.product_id, "quantity": item.quantity} for item in inp.items]
    with get_db_context() as db:
        result = svc_add_bill_items(db, inp.bill_id, items_list, store_id=store_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def update_bill_item(inp: UpdateBillItemInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        result = svc_update_bill_item(db, inp.bill_id, inp.item_id, inp.quantity, store_id=store_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)



def remove_bill_item(inp: RemoveBillItemInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        result = svc_remove_bill_item(db, inp.bill_id, inp.item_id, store_id=store_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def calculate_bill(inp: CalculateBillInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        result = svc_calculate_bill(db, inp.bill_id, store_id=store_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def finalize_bill(inp: FinalizeBillInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    idem_key = inp.idempotency_key or f"final_{inp.bill_id}_{uuid.uuid4().hex}"
    with get_db_context() as db:
        result = svc_finalize_bill(
            db,
            inp.bill_id,
            payment_method=inp.payment_method,
            payment_amount=inp.payment_amount,
            idempotency_key=idem_key,
            store_id=store_id,
        )
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)

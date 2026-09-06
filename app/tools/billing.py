# app/tools/billing.py
"""Tool handlers for billing-related actions.

Each function accepts the validated Pydantic input model from
``app.tools.schemas`` and calls the corresponding billing service function.
Results are returned as plain dicts (the registry wraps them in ToolResult).
"""

from app.services.billing_service import (
    create_draft_bill as svc_create_draft_bill,
    get_current_bill as svc_get_current_bill,
    add_bill_item as svc_add_bill_item,
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
    UpdateBillItemInput,
    RemoveBillItemInput,
    CalculateBillInput,
    FinalizeBillInput,
)


def create_draft_bill(inp: CreateDraftBillInput) -> dict:
    with get_db_context() as db:
        result = svc_create_draft_bill(
            db,
            customer_id=inp.customer_id,
            idempotency_key=inp.idempotency_key,
        )
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def get_current_bill(inp: GetCurrentBillInput) -> dict:
    with get_db_context() as db:
        result = svc_get_current_bill(db, inp.bill_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def add_bill_item(inp: AddBillItemInput) -> dict:
    with get_db_context() as db:
        result = svc_add_bill_item(db, inp.bill_id, inp.product_id, inp.quantity)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def update_bill_item(inp: UpdateBillItemInput) -> dict:
    with get_db_context() as db:
        result = svc_update_bill_item(db, inp.bill_id, inp.item_id, inp.quantity)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def remove_bill_item(inp: RemoveBillItemInput) -> dict:
    with get_db_context() as db:
        result = svc_remove_bill_item(db, inp.bill_id, inp.item_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def calculate_bill(inp: CalculateBillInput) -> dict:
    with get_db_context() as db:
        result = svc_calculate_bill(db, inp.bill_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def finalize_bill(inp: FinalizeBillInput) -> dict:
    with get_db_context() as db:
        result = svc_finalize_bill(
            db,
            inp.bill_id,
            payment_method=inp.payment_method,
            payment_amount=inp.payment_amount,
            idempotency_key=inp.idempotency_key,
        )
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)

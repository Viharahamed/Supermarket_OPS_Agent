# app/tools/preferences.py
"""Tool handlers for store owner preferences with store_id context."""

from typing import Any, Optional
from app.db.database import get_db_context
from app.db.models import OwnerPreference
from app.tools.schemas import (
    GetPreferenceInput,
    SetPreferenceInput,
)


def _extract_store_id(context: Optional[Any]) -> int:
    if context and hasattr(context, "principal") and context.principal:
        return context.principal.store_id
    return 1


def get_user_preferences(inp: GetPreferenceInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        pref = db.query(OwnerPreference).filter(
            OwnerPreference.store_id == store_id,
            OwnerPreference.key == inp.key,
        ).first()
        if not pref:
            return {"key": inp.key, "value": None}
        return {"key": pref.key, "value": pref.value}


def update_user_preferences(inp: SetPreferenceInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        pref = db.query(OwnerPreference).filter(
            OwnerPreference.store_id == store_id,
            OwnerPreference.key == inp.key,
        ).first()
        if not pref:
            pref = OwnerPreference(store_id=store_id, key=inp.key, value=inp.value)
            db.add(pref)
        else:
            pref.value = inp.value
        db.commit()
        return {"key": pref.key, "value": pref.value}

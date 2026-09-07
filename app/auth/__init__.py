"""Auth package for Kirana AI Agent."""
from app.auth.schemas import AuthenticatedPrincipal, ToolExecutionContext
from app.auth.service import (
    authenticate_telegram_user,
    bootstrap_store_and_user,
    check_authorization,
    get_or_create_default_store,
    require_operator,
    require_owner,
    require_role,
)

__all__ = [
    "AuthenticatedPrincipal",
    "ToolExecutionContext",
    "authenticate_telegram_user",
    "bootstrap_store_and_user",
    "check_authorization",
    "get_or_create_default_store",
    "require_operator",
    "require_owner",
    "require_role",
]

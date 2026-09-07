"""Authentication and Principal schemas for Kirana AI Agent."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class AuthenticatedPrincipal(BaseModel):
    """Domain model representing an authenticated user/operator and their store context."""
    user_id: int = Field(..., description="Unique User ID")
    store_id: int = Field(..., description="Canonical Store ID boundary")
    role: str = Field("OPERATOR", description="Operator role ('OWNER' or 'OPERATOR')")
    telegram_user_id: Optional[int] = Field(None, description="Telegram User ID if authenticated via Telegram")
    name: str = Field("Store Operator", description="Display name of the user")


class ToolExecutionContext(BaseModel):
    """Trusted execution context passed into tool execution handlers."""
    principal: AuthenticatedPrincipal = Field(..., description="Authenticated principal executing the tool")
    db: Optional[Any] = Field(None, description="Optional SQLAlchemy database session")

    class Config:
        arbitrary_types_allowed = True

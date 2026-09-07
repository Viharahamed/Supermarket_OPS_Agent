"""Authentication and Principal schemas for Kirana AI Agent."""
from typing import Any, Dict, Optional, Set
from pydantic import BaseModel, ConfigDict, Field


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
    user_message: Optional[str] = Field(None, description="Original user prompt text for current run")
    grounded_product_ids: Set[int] = Field(default_factory=set, description="Product IDs grounded via search_products in the current run")
    grounded_product_queries: Dict[int, Set[str]] = Field(default_factory=dict, description="Map of product_id -> set of normalized queries that returned it")

    model_config = ConfigDict(arbitrary_types_allowed=True)

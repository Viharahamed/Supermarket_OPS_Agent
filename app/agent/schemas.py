# app/agent/schemas.py

"""Pydantic schemas for the internal agent communication.

These models define the JSON structures that the LLM must emit and that the
agent loop validates before performing any action.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentAction(BaseModel):
    """Structured action emitted by the LLM.

    The `action_type` determines how the agent should react.
    """

    action_type: str = Field(..., description="One of: tool_call, final_response, clarification")
    tool_name: Optional[str] = Field(None, description="Snake_case identifier of the tool to call")
    arguments: Optional[Dict[str, Any]] = Field(
        None, description="Arguments for the tool call, validated against the tool's schema"
    )
    content: Optional[str] = Field(None, description="Final answer or clarification text")

    model_config = ConfigDict(extra="forbid")

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        allowed = {"tool_call", "final_response", "clarification"}
        if v not in allowed:
            raise ValueError(f"action_type must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def validate_action_fields(self) -> AgentAction:
        if self.action_type == "tool_call":
            if not self.tool_name:
                raise ValueError("tool_name is required for tool_call actions")
            if self.arguments is None:
                self.arguments = {}
        elif self.action_type in {"final_response", "clarification"}:
            if not self.content:
                raise ValueError("content is required for final_response or clarification actions")
        return self


class AgentResponse(BaseModel):
    """Result returned by the agent to the caller.

    Only the final user‑facing content is exposed – internal reasoning is
    omitted.
    """

    content: str = Field(..., description="Message to show to the end‑user")
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

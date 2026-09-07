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

    @model_validator(mode="before")
    @classmethod
    def normalize_action_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Reject any payload containing observation/result echo fields
        forbidden_echo_keys = {"data", "result", "observation", "success", "response", "status"}
        present_echo_keys = forbidden_echo_keys.intersection(data.keys())
        if present_echo_keys:
            raise ValueError(
                f"Payload contains observation/result echo fields {sorted(present_echo_keys)} and cannot be executed as an AgentAction."
            )

        # Safe normalization of legitimate alternative tool-call formats
        if ("name" in data or "tool" in data) and "tool_name" not in data:
            tool_name_val = data.get("name") or data.get("tool")

            args_val = data.get("arguments")
            if args_val is None:
                if "parameters" in data:
                    args_val = data.get("parameters")
                elif "args" in data:
                    args_val = data.get("args")

            if (
                isinstance(tool_name_val, str)
                and tool_name_val.strip()
                and isinstance(args_val, dict)
                and "content" not in data
            ):
                data_copy = dict(data)
                data_copy.pop("name", None)
                data_copy.pop("tool", None)
                data_copy.pop("parameters", None)
                data_copy.pop("args", None)
                data_copy["tool_name"] = tool_name_val
                data_copy["arguments"] = args_val
                if "action_type" not in data_copy:
                    data_copy["action_type"] = "tool_call"
                return data_copy

        return data

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

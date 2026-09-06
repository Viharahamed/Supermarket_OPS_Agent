# app/tools/result.py
"""Standardised result and error models for all tool calls.

Each tool returns a ``ToolResult`` instance containing a ``success`` flag,
payload data (when successful) and a ``ToolError`` (when failed). This uniform
shape is consumed by the future Gemma‑2 agent harness.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ToolError(BaseModel):
    """Machine‑readable error information returned by a tool.

    ``code`` is a short identifier such as ``PRODUCT_NOT_FOUND`` and ``message``
    is a human‑readable description. ``details`` can hold any additional data
    the caller may need.
    """

    code: str
    message: str
    details: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class ToolResult(BaseModel):
    """Uniform response wrapper for every tool.

    - ``success``: ``True`` when the operation succeeded.
    - ``data``:   Payload returned by the underlying service (present only when
      ``success`` is ``True``).
    - ``error``:  ``ToolError`` describing why the call failed.
    """

    success: bool
    data: Optional[Any] = None
    error: Optional[ToolError] = None

    model_config = ConfigDict(from_attributes=True)

# app/llm/base.py
"""Abstract Base Class for LLM Providers.

Defines the provider-independent interface required by the Kirana AI Agent loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from app.agent.schemas import AgentAction


class LLMProvider(ABC):
    """Abstract base class for all LLM providers (Ollama, OpenRouter, etc.)."""

    @abstractmethod
    def generate_action(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> AgentAction:
        """Call the underlying LLM API and parse a structured AgentAction response.

        Args:
            system_prompt: The detailed prompt specifying instructions and tool schemas.
            messages: List of conversation role/content dicts (user, assistant observations).

        Returns:
            Validated AgentAction Pydantic model.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMUnavailableError: If the service cannot be reached.
            LLMAuthenticationError: If API credentials are invalid/missing.
            ModelNotFoundError: If the requested model is unavailable.
            InvalidModelResponseError: If the LLM response fails AgentAction validation.
        """
        pass

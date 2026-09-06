# app/llm/factory.py
"""LLM Provider Factory.

Creates and configures the appropriate LLMProvider instance based on application settings.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import Settings, get_settings
from app.exceptions import KiranaException
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.openrouter import OpenRouterProvider

logger = logging.getLogger("app.llm.factory")


def get_llm_provider(settings: Optional[Settings] = None) -> LLMProvider:
    """Create an LLMProvider instance matching application configuration.

    Args:
        settings: Optional Settings object. If omitted, uses get_settings().

    Returns:
        LLMProvider instance.

    Raises:
        KiranaException: If LLM_PROVIDER is unsupported/unknown.
        LLMAuthenticationError: If OpenRouter is configured without an API key.
    """
    cfg = settings or get_settings()
    provider_name = (cfg.llm_provider or "ollama").lower().strip()

    logger.info(f"Initializing LLM Provider: '{provider_name}'")

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_model,
            timeout=cfg.ollama_timeout,
        )

    if provider_name == "openrouter":
        return OpenRouterProvider(
            base_url=cfg.openrouter_base_url,
            api_key=cfg.openrouter_api_key,
            model=cfg.openrouter_model,
            timeout=cfg.openrouter_timeout,
        )

    logger.error(f"Unknown LLM_PROVIDER specified: '{cfg.llm_provider}'")
    raise KiranaException(
        f"Unknown LLM_PROVIDER '{cfg.llm_provider}'. Supported options are 'ollama' or 'openrouter'.",
        code="CONFIG_ERROR",
    )

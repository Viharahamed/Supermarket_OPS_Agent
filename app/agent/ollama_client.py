# app/agent/ollama_client.py
"""Ollama LLM Client wrapper for backward compatibility.

Delegates to ``app.llm.ollama.OllamaProvider``.
"""

from __future__ import annotations

from app.llm.ollama import OllamaProvider

class OllamaClient(OllamaProvider):
    """Backward compatible wrapper for OllamaProvider."""
    pass

# app/agent/ollama_client.py

"""Ollama LLM Client for Gemma 2.

Handles communication with the local Ollama daemon, sends structured prompts,
and parses responses into ``AgentAction`` Pydantic models.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from app.agent.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
from app.agent.schemas import AgentAction
from app.exceptions import (
    InvalidModelResponseError,
    ModelNotFoundError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)

logger = logging.getLogger("app.agent.ollama_client")


class OllamaClient:
    """Client for local Ollama service running Gemma 2."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: int = OLLAMA_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate_action(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> AgentAction:
        """Call Ollama chat API and parse structured ``AgentAction`` response."""
        url = f"{self.base_url}/api/chat"
        payload_messages = [{"role": "system", "content": system_prompt}]
        payload_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": payload_messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic action generation
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as err:
            logger.error(f"Ollama request timed out after {self.timeout}s: {err}")
            raise OllamaTimeoutError(f"Ollama request timed out after {self.timeout} seconds.") from err
        except requests.exceptions.ConnectionError as err:
            logger.error(f"Failed to connect to Ollama at {url}: {err}")
            raise OllamaUnavailableError(f"Could not connect to Ollama service at {self.base_url}.") from err
        except requests.exceptions.RequestException as err:
            logger.error(f"Ollama request failed: {err}")
            raise OllamaUnavailableError(f"Ollama request failed: {err}") from err

        if response.status_code == 404:
            logger.error(f"Model '{self.model}' not found in Ollama")
            raise ModelNotFoundError(self.model)

        if response.status_code != 200:
            logger.error(f"Ollama returned HTTP {response.status_code}: {response.text}")
            raise OllamaUnavailableError(f"Ollama returned status code {response.status_code}")

        try:
            res_data = response.json()
            raw_content = res_data.get("message", {}).get("content", "")
            action_data = json.loads(raw_content)
            return AgentAction.model_validate(action_data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Failed to parse model response into AgentAction: {exc}. Raw content: {raw_content if 'raw_content' in locals() else ''}")
            # Robust fallback extraction if JSON block is wrapped in Markdown codefence
            if "raw_content" in locals() and raw_content:
                cleaned = raw_content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                    cleaned = cleaned.strip()
                    try:
                        action_data = json.loads(cleaned)
                        return AgentAction.model_validate(action_data)
                    except Exception:
                        pass
            raise InvalidModelResponseError(f"Model response could not be parsed as valid AgentAction JSON: {exc}") from exc

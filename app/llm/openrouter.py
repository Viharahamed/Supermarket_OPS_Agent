# app/llm/openrouter.py
"""OpenRouter LLM Provider Implementation.

Handles communication with OpenRouter API endpoint and maps vendor-specific HTTP status
codes and timeouts to Kirana application exception hierarchy.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import requests

from app.agent.schemas import AgentAction
from app.exceptions import (
    InvalidModelResponseError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMUnavailableError,
    ModelNotFoundError,
)
from app.llm.base import LLMProvider

logger = logging.getLogger("app.llm.openrouter")


class OpenRouterProvider(LLMProvider):
    """LLM Provider for OpenRouter API."""

    def __init__(
        self,
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        model: str = "qwen/qwen-2.5-72b-instruct",
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model
        self.timeout = timeout

        if not self.api_key:
            logger.error("OPENROUTER_API_KEY is missing or empty when LLM_PROVIDER=openrouter")
            raise LLMAuthenticationError("OPENROUTER_API_KEY environment variable is required when LLM_PROVIDER=openrouter.")

    def generate_action(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> AgentAction:
        """Call OpenRouter /chat/completions endpoint and parse AgentAction response."""
        url = f"{self.base_url}/chat/completions"
        payload_messages = [{"role": "system", "content": system_prompt}]
        payload_messages.extend(messages)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://kirana-ai-agent.local",
            "X-Title": "Kirana AI Agent",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0.1,
            "provider": {
                "require_parameters": True,
            },
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_action",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "action_type": {
                                "type": "string",
                                "enum": ["tool_call", "final_response", "clarification"],
                            },
                            "tool_name": {
                                "type": ["string", "null"],
                            },
                            "arguments": {
                                "type": ["object", "null"],
                            },
                            "content": {
                                "type": ["string", "null"],
                            },
                        },
                        "required": ["action_type", "tool_name", "arguments", "content"],
                        "additionalProperties": False,
                    },
                },
            },
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as err:
            logger.error(f"OpenRouter request timed out after {self.timeout}s: {err}")
            raise LLMTimeoutError(f"OpenRouter request timed out after {self.timeout} seconds.") from err
        except requests.exceptions.ConnectionError as err:
            logger.error(f"Failed to connect to OpenRouter at {url}: {err}")
            raise LLMUnavailableError(f"Could not connect to OpenRouter service at {self.base_url}.") from err
        except requests.exceptions.RequestException as err:
            logger.error(f"OpenRouter request failed: {err}")
            raise LLMUnavailableError(f"OpenRouter request failed: {err}") from err

        if response.status_code in {401, 403}:
            logger.error(f"OpenRouter authentication failed (HTTP {response.status_code})")
            raise LLMAuthenticationError(f"OpenRouter authentication failed (HTTP {response.status_code}). Please verify OPENROUTER_API_KEY.")

        if response.status_code == 404:
            logger.error(f"Model '{self.model}' not found on OpenRouter")
            raise ModelNotFoundError(self.model)

        if response.status_code != 200:
            logger.error(f"OpenRouter returned HTTP {response.status_code}: {response.text}")
            raise LLMUnavailableError(f"OpenRouter returned status code {response.status_code}")

        try:
            res_data = response.json()
            choices = res_data.get("choices", [])
            if not choices:
                raise InvalidModelResponseError("OpenRouter response contained empty choices array.")

            raw_content = choices[0].get("message", {}).get("content", "")
            action_data = json.loads(raw_content)
            return AgentAction.model_validate(action_data)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                f"Failed to parse OpenRouter response into AgentAction: {exc}. Raw content: {raw_content if 'raw_content' in locals() else ''}"
            )
            # Fallback extraction if output is inside code blocks
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

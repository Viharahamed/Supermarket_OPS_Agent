# tests/test_llm_providers.py
"""Unit and integration tests for LLM Provider Abstraction.

Verifies provider instantiation, factory selection, error mapping, structured output
validation, and Agent integration using mocks/fakes.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from app.agent.agent import Agent
from app.agent.schemas import AgentAction
from app.config import Settings
from app.exceptions import (
    KiranaException,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMUnavailableError,
    ModelNotFoundError,
    InvalidModelResponseError,
    OllamaTimeoutError,
)
from app.llm import (
    LLMProvider,
    OllamaProvider,
    OpenRouterProvider,
    get_llm_provider,
)


# -----------------------------------------------------------------------------
# A & B: Instantiation Tests
# -----------------------------------------------------------------------------

def test_ollama_provider_instantiation():
    """Test A: OllamaProvider can be instantiated with default and custom settings."""
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen3:1.7b", timeout=30)
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "qwen3:1.7b"
    assert provider.timeout == 30


def test_openrouter_provider_instantiation():
    """Test B: OpenRouterProvider can be instantiated when API key is provided."""
    provider = OpenRouterProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-test-key",
        model="qwen/qwen-2.5-72b-instruct",
        timeout=45,
    )
    assert provider.api_key == "sk-or-test-key"
    assert provider.model == "qwen/qwen-2.5-72b-instruct"


# -----------------------------------------------------------------------------
# C, D, E, F: Factory Tests
# -----------------------------------------------------------------------------

def test_factory_returns_ollama():
    """Test C: Factory returns OllamaProvider when LLM_PROVIDER=ollama."""
    settings = Settings(LLM_PROVIDER="ollama", OLLAMA_MODEL="qwen3:1.7b")
    provider = get_llm_provider(settings)
    assert isinstance(provider, OllamaProvider)


def test_factory_returns_openrouter():
    """Test D: Factory returns OpenRouterProvider when LLM_PROVIDER=openrouter."""
    settings = Settings(
        LLM_PROVIDER="openrouter",
        OPENROUTER_API_KEY="sk-or-dummy-key",
        OPENROUTER_MODEL="qwen/qwen-2.5-72b-instruct",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenRouterProvider)


def test_factory_unknown_provider_fails():
    """Test E: Unknown provider (LLM_PROVIDER=invalid) fails clearly."""
    settings = Settings(LLM_PROVIDER="invalid_vendor")
    with pytest.raises(KiranaException) as exc_info:
        get_llm_provider(settings)
    assert exc_info.value.code == "CONFIG_ERROR"
    assert "Unknown LLM_PROVIDER" in exc_info.value.message


def test_missing_openrouter_api_key_fails():
    """Test F: Missing OpenRouter API key fails when OpenRouter is selected."""
    settings = Settings(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="")
    with pytest.raises(LLMAuthenticationError) as exc_info:
        get_llm_provider(settings)
    assert "OPENROUTER_API_KEY" in str(exc_info.value)


# -----------------------------------------------------------------------------
# G, H, I, J, K: Exception Mapping & Validation Tests
# -----------------------------------------------------------------------------

@patch("requests.post")
def test_ollama_timeout_mapped(mock_post):
    """Test G: Ollama timeout maps to OllamaTimeoutError / LLMTimeoutError."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    provider = OllamaProvider()
    with pytest.raises(LLMTimeoutError):
        provider.generate_action("System prompt", [{"role": "user", "content": "hi"}])


@patch("requests.post")
def test_openrouter_timeout_mapped(mock_post):
    """Test H: OpenRouter timeout maps to LLMTimeoutError."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    provider = OpenRouterProvider(api_key="sk-or-test")
    with pytest.raises(LLMTimeoutError):
        provider.generate_action("System prompt", [{"role": "user", "content": "hi"}])


@patch("requests.post")
def test_openrouter_authentication_failure(mock_post):
    """Test I: OpenRouter HTTP 401 returns LLMAuthenticationError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_post.return_value = mock_resp

    provider = OpenRouterProvider(api_key="invalid-key")
    with pytest.raises(LLMAuthenticationError):
        provider.generate_action("System prompt", [{"role": "user", "content": "hi"}])


@patch("requests.post")
def test_malformed_llm_response_rejected(mock_post):
    """Test J: Malformed LLM response is rejected with InvalidModelResponseError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"content": "not json content"}}
    mock_post.return_value = mock_resp

    provider = OllamaProvider()
    with pytest.raises(InvalidModelResponseError):
        provider.generate_action("System prompt", [{"role": "user", "content": "hi"}])


@patch("requests.post")
def test_agent_action_validation_strict(mock_post):
    """Test K: Invalid AgentAction JSON schema is strictly rejected."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Invalid action_type 'invalid_type'
    mock_resp.json.return_value = {"message": {"content": json.dumps({"action_type": "invalid_type", "content": "test"})}}
    mock_post.return_value = mock_resp

    provider = OllamaProvider()
    with pytest.raises(InvalidModelResponseError):
        provider.generate_action("System prompt", [{"role": "user", "content": "hi"}])


# -----------------------------------------------------------------------------
# L, M, N: Agent Integration Tests with Mocked Providers
# -----------------------------------------------------------------------------

def test_agent_runs_with_mocked_provider():
    """Test L: Agent operates cleanly with a generic mocked LLMProvider."""
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_action.return_value = AgentAction(
        action_type="final_response",
        content="Hello from mock provider!"
    )

    agent = Agent(llm_provider=mock_provider)
    response = agent.run("Hello store assistant")

    assert response.content == "Hello from mock provider!"
    mock_provider.generate_action.assert_called_once()


def test_agent_operates_with_mocked_ollama_provider():
    """Test M: Agent operates with a mocked OllamaProvider."""
    mock_provider = MagicMock(spec=OllamaProvider)
    mock_provider.generate_action.return_value = AgentAction(
        action_type="final_response",
        content="Ollama mock response"
    )

    agent = Agent(llm_provider=mock_provider)
    response = agent.run("Test Ollama agent integration")

    assert response.content == "Ollama mock response"
    assert response.metadata["iterations"] == 1


def test_agent_operates_with_mocked_openrouter_provider():
    """Test N: Agent operates with a mocked OpenRouterProvider."""
    mock_provider = MagicMock(spec=OpenRouterProvider)
    mock_provider.generate_action.return_value = AgentAction(
        action_type="final_response",
        content="OpenRouter mock response"
    )

    agent = Agent(llm_provider=mock_provider)
    response = agent.run("Test OpenRouter agent integration")

    assert response.content == "OpenRouter mock response"
    assert response.metadata["iterations"] == 1


# -----------------------------------------------------------------------------
# O: Live Provider Smoke Tests (Gated by RUN_LLM_SMOKE_TESTS=true)
# -----------------------------------------------------------------------------

@pytest.mark.skipif(
    os.getenv("RUN_LLM_SMOKE_TESTS", "false").lower() != "true",
    reason="Live LLM smoke tests disabled by default. Enable with RUN_LLM_SMOKE_TESTS=true",
)
def test_live_provider_smoke():
    """Test O: Live smoke test against configured provider if enabled."""
    provider = get_llm_provider()
    action = provider.generate_action(
        system_prompt="Respond ONLY with JSON: {\"action_type\": \"final_response\", \"content\": \"smoke test ok\"}",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert action.action_type == "final_response"

# tests/test_config.py
"""Comprehensive Unit Tests for Production Configuration System (Phase 13A.2).

Verifies central Settings class, environment-aware validations, CORS parsing,
LLM provider configuration, production strictness, and security secret masking.
"""

import os
from unittest.mock import patch
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_config_development_defaults():
    """Verify default values for development environment."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.app_name == "kirana-ai-agent"
        assert settings.app_env == "development"
        assert settings.debug is True
        assert settings.log_level == "INFO"
        assert settings.llm_provider == "ollama"
        assert settings.database_url == "sqlite:///./data/kirana.db"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.agent_max_iterations == 8
        assert settings.timezone == "Asia/Kolkata"
        assert settings.document_storage == "local"
        assert settings.local_document_dir == "generated"
        assert settings.cors_origins == ["http://localhost:3000"]



def test_config_test_environment():
    """Verify configuration parsing in test environment."""
    with patch.dict(os.environ, {"APP_ENV": "test", "DEBUG": "false"}):
        settings = Settings(_env_file=None)
        assert settings.app_env == "test"
        assert settings.debug is False


def test_config_ollama_provider_settings():
    """Verify Ollama provider configuration settings."""
    env = {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://ollama-server:11434",
        "OLLAMA_MODEL": "qwen3:8b",
        "OLLAMA_TIMEOUT": "120",
    }
    with patch.dict(os.environ, env):
        settings = Settings(_env_file=None)
        assert settings.llm_provider == "ollama"
        assert settings.ollama_base_url == "http://ollama-server:11434"
        assert settings.ollama_model == "qwen3:8b"
        assert settings.ollama_timeout == 120


def test_config_openrouter_provider_settings():
    """Verify OpenRouter provider configuration settings."""
    env = {
        "LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "sk-or-v1-testkey12345",
        "OPENROUTER_MODEL": "openai/gpt-4o",
        "OPENROUTER_TIMEOUT": "45",
    }
    with patch.dict(os.environ, env):
        settings = Settings(_env_file=None)
        assert settings.llm_provider == "openrouter"
        assert settings.openrouter_api_key == "sk-or-v1-testkey12345"
        assert settings.openrouter_model == "openai/gpt-4o"
        assert settings.openrouter_timeout == 45


def test_config_invalid_llm_provider_rejection():
    """Verify that an unsupported LLM_PROVIDER is rejected by get_llm_provider."""
    from app.exceptions import KiranaException
    from app.llm.factory import get_llm_provider

    settings = Settings(LLM_PROVIDER="unsupported_llm", _env_file=None)
    with pytest.raises(KiranaException) as exc_info:
        get_llm_provider(settings)
    assert exc_info.value.code == "CONFIG_ERROR"
    assert "Unknown LLM_PROVIDER" in exc_info.value.message


def test_config_production_disallows_debug():
    """Verify production environment rejects DEBUG=True."""
    env = {"APP_ENV": "production", "DEBUG": "true"}
    with patch.dict(os.environ, env):
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)
        assert "DEBUG must be False in production" in str(exc_info.value)


def test_config_production_openrouter_key_required():
    """Verify production environment requires OPENROUTER_API_KEY when LLM_PROVIDER=openrouter."""
    env = {
        "APP_ENV": "production",
        "DEBUG": "false",
        "LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "",
    }
    with patch.dict(os.environ, env):
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)
        assert "OPENROUTER_API_KEY is required in production" in str(exc_info.value)


def test_config_database_url_setting():
    """Verify custom DATABASE_URL configuration."""
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./custom/path.db"}):
        settings = Settings(_env_file=None)
        assert settings.database_url == "sqlite:///./custom/path.db"


def test_config_agent_max_iterations():
    """Verify custom AGENT_MAX_ITERATIONS setting."""
    with patch.dict(os.environ, {"AGENT_MAX_ITERATIONS": "15"}):
        settings = Settings(_env_file=None)
        assert settings.agent_max_iterations == 15


def test_config_timezone_setting():
    """Verify custom TIMEZONE setting."""
    with patch.dict(os.environ, {"TIMEZONE": "Asia/Kolkata"}):
        settings = Settings(_env_file=None)
        assert settings.timezone == "Asia/Kolkata"


def test_config_document_storage_settings():
    """Verify document storage directory settings."""
    env = {"DOCUMENT_STORAGE": "local", "LOCAL_DOCUMENT_DIR": "my_reports"}
    with patch.dict(os.environ, env):
        settings = Settings(_env_file=None)
        assert settings.document_storage == "local"
        assert settings.local_document_dir == "my_reports"


def test_config_cors_origins_parsing():
    """Verify parsing comma-separated CORS_ORIGINS string into a list of origins."""
    env = {"CORS_ORIGINS": "http://localhost:3000, https://kirana.store, https://admin.kirana.store"}
    with patch.dict(os.environ, env):
        settings = Settings(_env_file=None)
        assert settings.cors_origins == [
            "http://localhost:3000",
            "https://kirana.store",
            "https://admin.kirana.store",
        ]


def test_config_secrets_masked_in_repr():
    """Verify sensitive fields (OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN) are masked in string representation."""
    env = {
        "OPENROUTER_API_KEY": "sk-or-secret-api-key-9999",
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    }
    with patch.dict(os.environ, env):
        settings = Settings(_env_file=None)
        repr_str = repr(settings)

        assert "sk-or-secret-api-key-9999" not in repr_str
        assert "123456789:ABCdefGHIjklMNOpqrsTUVwxyz" not in repr_str
        assert "***MASKED***" in repr_str

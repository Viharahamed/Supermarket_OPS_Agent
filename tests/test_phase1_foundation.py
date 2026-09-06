import pytest
from app.config import Settings, get_settings
from app.ollama_client import OllamaClient

def test_settings_defaults():
    settings = get_settings()
    assert settings.ollama_base_url is not None
    assert settings.ollama_model is not None
    assert settings.database_url is not None

def test_ollama_client_init():
    client = OllamaClient(base_url="http://localhost:11434", model="qwen3:8b")
    assert client.base_url == "http://localhost:11434"
    assert client.model == "qwen3:8b"

def test_ollama_health_structure():
    client = OllamaClient()
    health = client.check_health()
    assert isinstance(health, dict)
    assert "status" in health

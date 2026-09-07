# tests/test_telegram_webhook.py
"""Comprehensive Unit and Integration Tests for Phase 15 Telegram Webhook & Lifecycle.

Tests:
1. POST /telegram/webhook route presence.
2. GET /telegram/webhook rejection (HTTP 405).
3. Missing X-Telegram-Bot-Api-Secret-Token header rejection (HTTP 403).
4. Invalid secret token header rejection (HTTP 403).
5. Valid secret token header + valid Telegram update payload processing (HTTP 200).
6. Malformed JSON payload rejection (HTTP 400).
7. Settings validation: TELEGRAM_MODE=webhook requiring secret and HTTPS base URL.
8. Settings validation: TELEGRAM_MODE=polling requiring no webhook secret.
9. FastAPI lifespan Telegram Application startup & shutdown lifecycle.
10. Health and readiness probe independence.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.main import app
from app.config import Settings


# -----------------------------------------------------------------------------
# 1. FastAPI Webhook Route & Secret Validation Tests
# -----------------------------------------------------------------------------

def test_webhook_rejects_get_requests():
    """Verify GET requests to /telegram/webhook are rejected with HTTP 405."""
    client = TestClient(app)
    response = client.get("/telegram/webhook")
    assert response.status_code == 405


def test_webhook_rejects_missing_secret_header():
    """Verify POST requests without secret token header are rejected with HTTP 403."""
    with patch("app.api.routes.telegram_webhook.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.telegram_mode = "webhook"
        mock_settings.telegram_webhook_secret = "correct_secret_token_123"
        mock_get_settings.return_value = mock_settings

        client = TestClient(app)
        response = client.post("/telegram/webhook", json={"update_id": 10001})
        assert response.status_code == 403
        assert "Invalid or missing X-Telegram-Bot-Api-Secret-Token" in response.json()["detail"]


def test_webhook_rejects_invalid_secret_header():
    """Verify POST requests with incorrect secret token header are rejected with HTTP 403."""
    with patch("app.api.routes.telegram_webhook.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.telegram_mode = "webhook"
        mock_settings.telegram_webhook_secret = "correct_secret_token_123"
        mock_get_settings.return_value = mock_settings

        client = TestClient(app)
        headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_secret_token_999"}
        response = client.post("/telegram/webhook", json={"update_id": 10001}, headers=headers)
        assert response.status_code == 403
        assert "Invalid or missing X-Telegram-Bot-Api-Secret-Token" in response.json()["detail"]


def test_webhook_accepts_valid_secret_and_processes_update():
    """Verify POST with valid secret token parses Update and calls application.process_update()."""
    with patch("app.api.routes.telegram_webhook.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.telegram_mode = "webhook"
        mock_settings.telegram_webhook_secret = "correct_secret_token_123"
        mock_get_settings.return_value = mock_settings

        mock_telegram_app = MagicMock()
        mock_telegram_app.bot = MagicMock()
        mock_telegram_app.bot.defaults = None
        mock_telegram_app.process_update = AsyncMock()

        client = TestClient(app)
        app.state.telegram_app = mock_telegram_app

        headers = {"X-Telegram-Bot-Api-Secret-Token": "correct_secret_token_123"}
        update_payload = {
            "update_id": 10001,
            "message": {
                "message_id": 50,
                "date": 1700000000,
                "chat": {"id": 12345, "type": "private"},
                "from": {"id": 12345, "is_bot": False, "first_name": "TestUser"},
                "text": "How much Maggi is left?",
            },
        }

        response = client.post("/telegram/webhook", json=update_payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["update_id"] == 10001
        mock_telegram_app.process_update.assert_called_once()


def test_webhook_rejects_malformed_json():
    """Verify non-JSON body payload returns HTTP 400 Bad Request."""
    with patch("app.api.routes.telegram_webhook.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.telegram_mode = "webhook"
        mock_settings.telegram_webhook_secret = "secret_123"
        mock_get_settings.return_value = mock_settings

        mock_telegram_app = MagicMock()
        app.state.telegram_app = mock_telegram_app

        client = TestClient(app)
        headers = {
            "X-Telegram-Bot-Api-Secret-Token": "secret_123",
            "Content-Type": "application/json",
        }
        response = client.post("/telegram/webhook", content="invalid json string {", headers=headers)
        assert response.status_code == 400
        assert "Malformed JSON" in response.json()["detail"]


# -----------------------------------------------------------------------------
# 2. Configuration Settings Validation Tests
# -----------------------------------------------------------------------------

def test_config_webhook_mode_validation_missing_secret():
    """Verify TELEGRAM_MODE=webhook without TELEGRAM_WEBHOOK_SECRET raises ValidationError."""
    env_vars = {
        "TELEGRAM_MODE": "webhook",
        "TELEGRAM_WEBHOOK_SECRET": "",
        "PUBLIC_BASE_URL": "https://kirana-bot.up.railway.app",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_SECRET is required"):
            Settings(_env_file=None)


def test_config_webhook_mode_validation_missing_https():
    """Verify TELEGRAM_MODE=webhook with non-HTTPS PUBLIC_BASE_URL raises ValidationError."""
    env_vars = {
        "TELEGRAM_MODE": "webhook",
        "TELEGRAM_WEBHOOK_SECRET": "secret_123",
        "PUBLIC_BASE_URL": "http://insecure-domain.com",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        with pytest.raises(ValueError, match="PUBLIC_BASE_URL must start with 'https://'"):
            Settings(_env_file=None)


def test_config_polling_mode_validation_no_secret_required():
    """Verify TELEGRAM_MODE=polling passes validation without secret or public base URL."""
    env_vars = {
        "TELEGRAM_MODE": "polling",
        "TELEGRAM_WEBHOOK_SECRET": "",
        "PUBLIC_BASE_URL": "",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        settings = Settings(_env_file=None)
        assert settings.telegram_mode == "polling"


# -----------------------------------------------------------------------------
# 3. FastAPI Lifespan & Application Lifecycle Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fastapi_lifespan_webhook_app_lifecycle():
    """Verify FastAPI lifespan initializes and shuts down Telegram Application when TELEGRAM_MODE=webhook."""
    from app.api.main import lifespan

    mock_telegram_app = AsyncMock()
    mock_telegram_app.initialize = AsyncMock()
    mock_telegram_app.start = AsyncMock()
    mock_telegram_app.stop = AsyncMock()
    mock_telegram_app.shutdown = AsyncMock()

    with patch("app.api.main.settings") as mock_settings, \
         patch("app.telegram.bot.build_application", return_value=mock_telegram_app):
        mock_settings.telegram_mode = "webhook"
        test_app = FastAPI()

        async with lifespan(test_app):
            mock_telegram_app.initialize.assert_called_once()
            mock_telegram_app.start.assert_called_once()
            assert test_app.state.telegram_app == mock_telegram_app

        mock_telegram_app.stop.assert_called_once()
        mock_telegram_app.shutdown.assert_called_once()


def test_health_and_readiness_endpoints_unaffected():
    """Verify /health liveness and /ready readiness endpoints remain fast and unaffected."""
    client = TestClient(app)
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


def test_bot_main_disables_polling_in_webhook_mode(capsys):
    """Verify bot.main() detects TELEGRAM_MODE=webhook and exits without launching polling loop."""
    from app.telegram.bot import main as bot_main

    with patch("app.telegram.bot.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.telegram_mode = "webhook"
        mock_get_settings.return_value = mock_settings

        # Invoke bot.main() in webhook mode
        bot_main()
        captured = capsys.readouterr()
        assert "Local polling is disabled" in captured.out or "TELEGRAM_MODE is configured as 'webhook'" in captured.out


@pytest.mark.asyncio
async def test_delete_webhook_script():
    """Verify scripts/delete_webhook.py calls bot.delete_webhook() safely."""
    from scripts.delete_webhook import delete_webhook_async

    mock_bot = AsyncMock()
    mock_bot.delete_webhook = AsyncMock(return_value=True)
    mock_bot.get_webhook_info = AsyncMock()

    with patch("scripts.delete_webhook.get_settings") as mock_get_settings, \
         patch("scripts.delete_webhook.Bot", return_value=mock_bot):
        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = "123456:ABC-DEF1234ghIkl-zyx57"
        mock_get_settings.return_value = mock_settings

        await delete_webhook_async()
        mock_bot.delete_webhook.assert_called_once()


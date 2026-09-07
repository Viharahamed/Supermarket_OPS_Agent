# 🚀 Implementation Plan — Phase 15: Telegram Webhook + Production Railway Deployment

Moving the Telegram bot from local polling (`TELEGRAM_MODE=polling`) to production webhook operation (`TELEGRAM_MODE=webhook`) on Railway, while preserving 100% backward compatibility for local polling during development.

---

## 🎯 Architectural Overview

```
[Production Webhook Flow]
Telegram Platform
   │
   ▼ HTTPS POST (Header: X-Telegram-Bot-Api-Secret-Token)
Railway FastAPI App (POST /telegram/webhook)
   │
   ├── 1. Validate Secret Token Header (HTTP 403 if invalid)
   ├── 2. Convert JSON payload to telegram.Update object
   ▼
Telegram Application (python-telegram-bot)
   │
   ▼
Existing Handlers (app/telegram/handlers.py)
   │
   ├── Phase 14 Telegram User Authentication (users table)
   ├── Context Construction (ToolExecutionContext + AuthenticatedPrincipal)
   ▼
Agent Harness (app/agent/) -> Tool Registry -> Services -> PostgreSQL
```

---

## Proposed Changes

### Centralized Configuration Layer

#### [MODIFY] [app/config.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/config.py)
#### [MODIFY] [.env.example](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/.env.example)

- Add new setting fields:
  - `telegram_webhook_secret: str` (alias `TELEGRAM_WEBHOOK_SECRET`)
  - `public_base_url: str` (alias `PUBLIC_BASE_URL`)
- Update `validate_environment()`:
  - If `telegram_mode == "webhook"`:
    - Validate `telegram_webhook_secret` is non-empty.
    - Validate `public_base_url` is non-empty and starts with `https://`.
  - If `telegram_mode == "polling"`:
    - Webhook secret and public base URL are optional.
- Add `telegram_webhook_secret` masking to `Settings.__repr__()`.

---

### FastAPI Webhook Endpoint & Lifespan Management

#### [NEW] [app/api/routes/telegram_webhook.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/api/routes/telegram_webhook.py)
- `POST /telegram/webhook` endpoint:
  - Validates `X-Telegram-Bot-Api-Secret-Token` header against `settings.telegram_webhook_secret`. Returns HTTP 403 Forbidden on mismatch/missing header.
  - Receives raw JSON update payload (rejects malformed JSON with HTTP 400).
  - Retrieves `telegram_app` from `request.app.state.telegram_app`.
  - Converts raw JSON dict to `telegram.Update.de_json(data, telegram_app.bot)`.
  - Executes `await telegram_app.process_update(update)`.
  - Returns HTTP 200 `{"status": "ok"}`.
  - Excludes raw update payloads and user message contents from error logs to prevent secret / PII leakage.

#### [MODIFY] [app/api/main.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/api/main.py)
- Add FastAPI `lifespan` context manager:
  - On startup: if `TELEGRAM_MODE=webhook`, builds Telegram `Application` via `build_application()`, calls `await telegram_app.initialize()`, `await telegram_app.start()`, and stores instance in `app.state.telegram_app`.
  - On shutdown: if `TELEGRAM_MODE=webhook`, executes `await telegram_app.stop()`, `await telegram_app.shutdown()`.
- Include `telegram_webhook_router` into FastAPI app.

---

### Telegram Bot Runner & Webhook Registration

#### [MODIFY] [app/telegram/bot.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/bot.py)
- Update `main()` entrypoint:
  - Check `settings.telegram_mode`.
  - If `polling`: runs `app.run_polling()`.
  - If `webhook`: displays informative message that application is running in webhook mode via FastAPI/Uvicorn, and exits or refrains from polling.

#### [NEW] [scripts/register_webhook.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/scripts/register_webhook.py)
- Explicit CLI setup utility for production Telegram webhook registration:
  - Construct webhook URL: `f"{settings.public_base_url.rstrip('/')}/telegram/webhook"`.
  - Register webhook with Telegram API using `bot.set_webhook(url=..., secret_token=...)`.
  - Retrieve and log webhook status via `bot.get_webhook_info()` without exposing tokens or secrets.

---

### Documentation & Runbook

#### [MODIFY] [README.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md)
- Add Section for **Phase 15 — Telegram Webhook & Production Deployment**:
  - Local Polling mode vs Production Webhook mode.
  - Webhook secret configuration & HTTPS requirement.
  - Railway environment variables reference table.
  - Explicit Alembic schema migration guide (`railway run alembic upgrade head`).
  - Persistent Railway Volume mount configuration (`LOCAL_DOCUMENT_DIR`).
  - Production deployment runbook.

---

## 🧪 Verification Plan

### Automated Tests (`pytest -v`)
- Create `tests/test_telegram_webhook.py`:
  1. `test_webhook_route_exists`: Verify `POST /telegram/webhook` is registered.
  2. `test_webhook_rejects_get_requests`: `GET /telegram/webhook` returns HTTP 405.
  3. `test_webhook_rejects_missing_secret_header`: Missing `X-Telegram-Bot-Api-Secret-Token` header returns HTTP 403.
  4. `test_webhook_rejects_invalid_secret_header`: Invalid secret header returns HTTP 403.
  5. `test_webhook_accepts_valid_secret_and_processes_update`: Valid secret header + valid update JSON processes update successfully (returns HTTP 200).
  6. `test_webhook_rejects_malformed_json`: Malformed payload returns HTTP 400.
  7. `test_config_webhook_mode_validation_missing_secret`: Webhook mode without secret raises configuration error.
  8. `test_config_webhook_mode_validation_missing_https`: Webhook mode without HTTPS URL raises configuration error.
  9. `test_config_polling_mode_validation_no_secret_required`: Polling mode passes validation without secret.
  10. `test_fastapi_lifespan_webhook_app_lifecycle`: Verify FastAPI lifespan initializes and shuts down Telegram Application cleanly.
  11. `test_health_and_readiness_endpoints_unaffected`: Verify `/health` and `/ready` endpoints remain fast and unaffected by webhook state.

### Automated Test Baseline
- Ensure all existing 181 tests continue to pass (target: 190+ passing tests, 0 failures).

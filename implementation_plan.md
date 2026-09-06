# Implementation Plan - Phase 12 Telegram Bot Integration

Build a production-grade Telegram Bot interface (`python-telegram-bot` 21.x) layered strictly on top of the existing Kirana AI Agent engine, maintaining decoupling, strict error boundaries, safe HTML formatting, and session management.

## User Review Required

> [!IMPORTANT]
> - **Zero Database Mutation on `/new`**: Running `/new` will clear only the active conversational session history (`AgentSession`) for that specific user. Catalog products, stock movements, draft/finalized bills, customers, Khata ledger entries, and store preferences remain completely untouched.
> - **Decoupled Architecture**: The Telegram layer will NOT directly access SQLAlchemy or database repositories. All message routing and session resets pass strictly through `app.agent` functions (`handle_message`, `clear_session`).
> - **Environment Configuration**: The bot token is loaded securely from `TELEGRAM_BOT_TOKEN` via `app.config.get_settings()`.

## Proposed Changes

### Agent Layer Session Management

#### [MODIFY] [__init__.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/agent/__init__.py)
- Export `clear_session(user_id: int) -> bool` to reset conversation history for a given user ID.

#### [MODIFY] [agent.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/agent/agent.py)
- Add session persistence & session clearing helper functions (`clear_session_history`) that operate on the `AgentSession` entity without modifying any store catalog or financial data.

---

### Telegram Interface Layer

#### [NEW] [__init__.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/__init__.py)
- Initialize the `telegram` package module.

#### [NEW] [handlers.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/handlers.py)
- Implement handler functions:
  - `start_command(update, context)`: Welcome greeting & Kirana store management overview.
  - `help_command(update, context)`: Command guide with natural-language example queries (inventory, billing, khata, reports).
  - `new_command(update, context)`: Resets session history for `update.effective_user.id` via `clear_session()`.
  - `text_message_handler(update, context)`: Routes incoming text messages to `handle_message()`, formats responses with safe HTML, and handles message splitting if content exceeds Telegram's 4096-character limit.
  - `error_handler(update, context)`: Catches API, connection, Ollama, and application exceptions. Formats clean, user-friendly responses without exposing stack traces, internal prompts, SQL, or tokens.
  - Utility helpers: `escape_html()`, `format_telegram_response()`, `split_message()`.

#### [NEW] [bot.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/bot.py)
- Setup `python-telegram-bot` application:
  - Validates `TELEGRAM_BOT_TOKEN` environment variable.
  - Registers `/start`, `/help`, `/new` command handlers and message filters (`filters.TEXT & ~filters.COMMAND`).
  - Registers global error handler.
  - Exposes `main()` entry point to start the bot via polling (`python -m app.telegram.bot` or `python run_bot.py`).

---

### Documentation & Verification

#### [MODIFY] [README.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md)
- Add setup and execution guide:
  - Dependency installation (`python-telegram-bot`).
  - Environment variable setup (`TELEGRAM_BOT_TOKEN`).
  - Starting Ollama daemon (`ollama serve`).
  - Starting the Telegram bot process (`python -m app.telegram.bot`).
  - Testing `/start`, `/help`, `/new`, and sample natural-language queries.

#### [NEW] [test_telegram_bot.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/tests/test_telegram_bot.py)
- Create comprehensive test suite for Telegram integration:
  - `/start` command response.
  - `/help` command response.
  - `/new` session reset without deleting store catalog/stock/khata data.
  - Text message routing to `handle_message()`.
  - Safe HTML formatting & escaping.
  - Message splitting for long outputs (>4096 chars).
  - Exception & error handling (Ollama down, invalid tool args, application errors).

## Verification Plan

### Automated Tests
- Run `pytest -v` to ensure all existing 78 tests plus new Telegram bot unit/integration tests pass 100%.

### Manual Verification
- Verify CLI `python cli.py` still runs cleanly and remains unaffected.
- Verify environment loading of `TELEGRAM_BOT_TOKEN`.

# app/telegram/bot.py
"""Telegram Bot Runner for Kirana AI Agent.

Configures python-telegram-bot Application, registers handlers, and launches
polling loop.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from app.config import get_settings
from app.db.database import init_db
from app.telegram.handlers import (
    error_handler,
    help_command,
    new_command,
    start_command,
    text_message_handler,
)

logger = logging.getLogger("app.telegram.bot")


def build_application(token: str = None) -> Application:
    """Build and configure python-telegram-bot Application instance."""
    settings = get_settings()
    bot_token = token or settings.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing or empty! "
            "Please configure TELEGRAM_BOT_TOKEN in your .env file."
        )

    application = ApplicationBuilder().token(bot_token).build()

    # Register Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))

    # Register Text Message Handler (filters out commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    # Register Global Error Handler
    application.add_error_handler(error_handler)

    return application


def main() -> None:
    """Main entry point to start Kirana AI Agent Telegram Bot."""
    print("=" * 60)
    print("  🏪 KIRANA AI AGENT — TELEGRAM BOT RUNNER")
    print("=" * 60)

    # Initialize DB tables
    init_db()
    print("Database tables initialized.")

    try:
        app = build_application()
        print("Telegram bot configured successfully. Starting polling loop...")
        print("Press Ctrl+C to stop the bot.\n")
        app.run_polling()
    except ValueError as val_err:
        print(f"\n❌ Configuration Error: {val_err}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopping Kirana AI Agent Telegram Bot. Goodbye!")
    except Exception as exc:
        print(f"\n❌ Exception starting Telegram Bot: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

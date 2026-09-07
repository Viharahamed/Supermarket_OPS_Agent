# scripts/register_webhook.py
"""Controlled Setup Script to Register Telegram Webhook for Kirana AI Agent."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Bot
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("register_webhook")


async def register_webhook_async() -> None:
    """Register Telegram Webhook URL and secret token with Telegram Bot API."""
    settings = get_settings()

    if settings.telegram_mode.lower().strip() != "webhook":
        logger.warning(
            f"TELEGRAM_MODE is currently '{settings.telegram_mode}'. "
            "To use Webhooks, set TELEGRAM_MODE=webhook in environment."
        )

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        sys.exit(1)

    if not settings.telegram_webhook_secret:
        logger.error("TELEGRAM_WEBHOOK_SECRET is missing! Please configure a secure secret in environment.")
        sys.exit(1)

    if not settings.public_base_url or not settings.public_base_url.startswith("https://"):
        logger.error("PUBLIC_BASE_URL is missing or does not start with 'https://'!")
        sys.exit(1)

    webhook_url = f"{settings.public_base_url.rstrip('/')}/telegram/webhook"
    logger.info(f"Registering Telegram Webhook URL: '{webhook_url}'")

    bot = Bot(token=settings.telegram_bot_token)

    try:
        # Set webhook with secret token
        success = await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=False,
        )

        if success:
            logger.info("✅ Telegram Webhook registered successfully!")

            # Retrieve current webhook status
            info = await bot.get_webhook_info()
            logger.info("--- Webhook Status Info ---")
            logger.info(f"Webhook URL: {info.url}")
            logger.info(f"Custom Certificate: {info.has_custom_certificate}")
            logger.info(f"Pending Update Count: {info.pending_update_count}")
            if info.last_error_date:
                logger.warning(f"Last Error Date: {info.last_error_date}")
                logger.warning(f"Last Error Message: {info.last_error_message}")
            else:
                logger.info("Last Error: None")
        else:
            logger.error("❌ Telegram Webhook registration failed.")
            sys.exit(1)

    except Exception as exc:
        logger.error(f"❌ Exception during Telegram Webhook registration: {exc}")
        sys.exit(1)


def main() -> None:
    print("=" * 60)
    print("  🚀 KIRANA AI AGENT — TELEGRAM WEBHOOK REGISTRATION SETUP")
    print("=" * 60)
    asyncio.run(register_webhook_async())


if __name__ == "__main__":
    main()

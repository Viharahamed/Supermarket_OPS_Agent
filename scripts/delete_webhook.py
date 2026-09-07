# scripts/delete_webhook.py
"""Controlled Setup Script to Unregister/Delete Telegram Webhook for Kirana AI Agent."""

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
logger = logging.getLogger("delete_webhook")


async def delete_webhook_async() -> None:
    """Safely unregister/delete Telegram Webhook with Telegram Bot API."""
    settings = get_settings()

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        sys.exit(1)

    logger.info("Unregistering Telegram Webhook...")
    bot = Bot(token=settings.telegram_bot_token)

    try:
        success = await bot.delete_webhook(drop_pending_updates=False)

        if success:
            logger.info("✅ Telegram Webhook successfully removed!")
            info = await bot.get_webhook_info()
            logger.info("--- Current Webhook Status ---")
            logger.info(f"Webhook URL: '{info.url}' (Empty = Polling ready)")
            logger.info(f"Pending Update Count: {info.pending_update_count}")
        else:
            logger.error("❌ Failed to delete Telegram Webhook.")
            sys.exit(1)

    except Exception as exc:
        logger.error(f"❌ Exception during Telegram Webhook deletion: {exc}")
        sys.exit(1)


def main() -> None:
    print("=" * 60)
    print("  🗑️ KIRANA AI AGENT — TELEGRAM WEBHOOK DELETION SETUP")
    print("=" * 60)
    asyncio.run(delete_webhook_async())


if __name__ == "__main__":
    main()

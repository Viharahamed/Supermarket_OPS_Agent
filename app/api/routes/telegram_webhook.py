# app/api/routes/telegram_webhook.py
"""Telegram Webhook Route for Kirana AI Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request, status
from telegram import Update

from app.config import get_settings

logger = logging.getLogger("app.api.routes.telegram_webhook")
router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Receive Telegram Webhook Updates",
    description="Processes incoming Telegram Update payloads when TELEGRAM_MODE=webhook.",
)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default="", alias="X-Telegram-Bot-Api-Secret-Token"),
) -> Dict[str, Any]:
    """Validate secret token, convert payload to Telegram Update, and process update."""
    settings = get_settings()

    # Reject requests if secret token does not match configured TELEGRAM_WEBHOOK_SECRET
    if settings.telegram_mode == "webhook" or settings.telegram_webhook_secret:
        if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            logger.warning("Unauthorized Telegram webhook access attempt: invalid or missing secret token header.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing X-Telegram-Bot-Api-Secret-Token header.",
            )

    telegram_app = getattr(request.app.state, "telegram_app", None)
    if not telegram_app:
        logger.error("Telegram Application is not initialized in FastAPI application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram Application is not initialized for webhook updates.",
        )

    try:
        data = await request.json()
    except Exception as exc:
        logger.warning(f"Malformed JSON payload in webhook request: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON update payload.",
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram Update format. Expected JSON object.",
        )

    update = Update.de_json(data, telegram_app.bot)
    if not update:
        logger.warning("Failed to parse Telegram Update object from JSON payload.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse Telegram Update object.",
        )

    update_id = getattr(update, "update_id", "unknown")
    from app.logging_config import set_correlation_id
    set_correlation_id(f"corr_tg_{update_id}")
    logger.info(f"Processing Telegram Webhook update_id={update_id}")

    try:
        await telegram_app.process_update(update)
    except Exception as proc_err:
        logger.error(f"Error processing Telegram update_id={update_id}: {proc_err}", exc_info=True)
        # Return HTTP 200 to Telegram so Telegram does not continuously retry failing updates indefinitely
        return {"status": "error", "update_id": update_id, "message": "Update processing encountered an error."}

    return {"status": "ok", "update_id": update_id}

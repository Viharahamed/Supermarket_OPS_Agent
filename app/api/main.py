import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes.health import router as health_router
from app.api.routes.telegram_webhook import router as telegram_webhook_router

logger = logging.getLogger("app.api.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FastAPI application lifecycle and Telegram Webhook Application state."""
    if settings.telegram_mode.lower().strip() == "webhook":
        logger.info("Initializing Telegram Application for Webhook mode...")
        from app.telegram.bot import build_application
        telegram_app = build_application()
        await telegram_app.initialize()
        await telegram_app.start()
        app.state.telegram_app = telegram_app
        logger.info("Telegram Application successfully started for Webhook updates.")

    yield

    if hasattr(app.state, "telegram_app") and app.state.telegram_app:
        logger.info("Shutting down Telegram Application...")
        try:
            await app.state.telegram_app.stop()
            await app.state.telegram_app.shutdown()
            logger.info("Telegram Application shutdown complete.")
        except Exception as exc:
            logger.error(f"Error during Telegram Application shutdown: {exc}")


app = FastAPI(
    title=settings.app_name,
    description="Production HTTP application layer for Kirana AI Agent",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Configure CORS Middleware using centralized settings
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register API routes
app.include_router(health_router)
app.include_router(telegram_webhook_router)


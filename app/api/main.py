import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import setup_logging, set_correlation_id, clear_correlation_id
from app.api.routes.health import router as health_router
from app.api.routes.telegram_webhook import router as telegram_webhook_router

settings = get_settings()
setup_logging(settings.log_level, settings.app_env)

logger = logging.getLogger("app.api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage FastAPI application lifecycle and Telegram Webhook Application state."""
    logger.info(f"Starting {settings.app_name} in environment='{settings.app_env}', mode='{settings.telegram_mode}'")
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
    
    logger.info(f"Application {settings.app_name} shutdown complete.")


app = FastAPI(
    title=settings.app_name,
    description="Production HTTP application layer for Kirana AI Agent",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Inject or propagate correlation ID for all incoming HTTP requests."""
    corr_id = request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex[:12]}"
    set_correlation_id(corr_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
    finally:
        clear_correlation_id()


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

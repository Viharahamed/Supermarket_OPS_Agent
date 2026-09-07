# app/api/main.py
"""FastAPI Application Main Entrypoint for Kirana AI Agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes.health import router as health_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Production HTTP application layer for Kirana AI Agent",
    version="1.0.0",
    debug=settings.debug,
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

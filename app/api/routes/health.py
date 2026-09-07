# app/api/routes/health.py
"""Health and Readiness Monitoring Endpoints for Kirana AI Agent."""

import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.database import get_db_context

logger = logging.getLogger("app.api.health")
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Process Liveness Probe",
    description="Deterministic process liveness check. Returns HTTP 200 when the FastAPI application is alive.",
)
def check_health():
    """Liveness probe. Does not make external network or database calls."""
    return {"status": "ok"}


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Database Readiness Probe",
    description="Verifies operational readiness by querying database connectivity.",
)
def check_readiness():
    """Readiness probe. Checks database connectivity using a lightweight query."""
    try:
        with get_db_context() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.warning(f"Database readiness check failed: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready"},
        )

# tests/test_railway_config.py
"""Unit Tests for Railway Deployment Preparation (Phase 13A.6).

Verifies Railway PORT environment override, Railway postgres:// and postgresql:// URL
driver transformation to postgresql+psycopg://, production settings strictness,
platform-independent document path resolution, and liveness probe performance.
"""

import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import Settings, get_settings
from app.db.database import _configure_engine
from app.documents.invoice_pdf import _get_invoices_dir
from app.documents.sales_pptx import _get_reports_dirs

client = TestClient(app)


def _require_psycopg():
    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg PostgreSQL driver is not installed in the environment.")


def test_railway_postgres_url_normalization_postgres_prefix():
    """Verify postgres:// Railway connection string is converted to postgresql+psycopg:// dialect."""
    _require_psycopg()
    raw_railway_url = "postgres://postgres:password123@monorail.proxy.rlwy.net:12345/railway"
    expected_url = "postgresql+psycopg://postgres:password123@monorail.proxy.rlwy.net:12345/railway"
    
    engine = _configure_engine(raw_railway_url)
    assert engine.url.render_as_string(hide_password=False) == expected_url


def test_railway_postgres_url_normalization_postgresql_prefix():
    """Verify postgresql:// Railway connection string is converted to postgresql+psycopg:// dialect."""
    _require_psycopg()
    raw_railway_url = "postgresql://postgres:password123@monorail.proxy.rlwy.net:12345/railway"
    expected_url = "postgresql+psycopg://postgres:password123@monorail.proxy.rlwy.net:12345/railway"
    
    engine = _configure_engine(raw_railway_url)
    assert engine.url.render_as_string(hide_password=False) == expected_url


def test_railway_port_environment_override():
    """Verify that Railway runtime PORT environment variable overrides default host/port settings."""
    with patch.dict(os.environ, {"PORT": "9090", "HOST": "0.0.0.0"}):
        settings = Settings(_env_file=None)
        assert settings.port == 9090
        assert settings.host == "0.0.0.0"


def test_railway_production_settings_validation():
    """Verify strict validation rules when APP_ENV=production."""
    with patch.dict(os.environ, {
        "APP_ENV": "production",
        "DEBUG": "false",
        "LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "sk-or-v1-testkey123456789",
    }):
        settings = Settings(_env_file=None)
        assert settings.app_env == "production"
        assert settings.debug is False
        assert settings.openrouter_api_key == "sk-or-v1-testkey123456789"


def test_railway_production_debug_true_rejected():
    """Verify APP_ENV=production raises ValueError if DEBUG=true."""
    with patch.dict(os.environ, {
        "APP_ENV": "production",
        "DEBUG": "true",
    }):
        with pytest.raises(ValueError, match="DEBUG must be False in production environment"):
            Settings(_env_file=None)


def test_configurable_document_storage_paths(tmp_path: Path):
    """Verify document storage directories use configurable LOCAL_DOCUMENT_DIR path."""
    custom_dir = str(tmp_path / "custom_generated")
    get_settings.cache_clear()
    try:
        with patch.dict(os.environ, {"LOCAL_DOCUMENT_DIR": custom_dir}):
            inv_dir = _get_invoices_dir()
            reports_dir, temp_charts_dir = _get_reports_dirs()

            assert inv_dir == Path(custom_dir) / "invoices"
            assert reports_dir == Path(custom_dir) / "reports"
            assert temp_charts_dir == Path(custom_dir) / "reports" / "temp_charts"
            assert inv_dir.exists()
            assert reports_dir.exists()
            assert temp_charts_dir.exists()
    finally:
        get_settings.cache_clear()


def test_railway_liveness_healthcheck_endpoint():
    """Verify GET /health liveness probe returns HTTP 200 {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

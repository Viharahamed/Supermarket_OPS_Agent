# Walkthrough — Phase 13A.6: Railway Deployment Preparation

Successfully prepared the **Kirana AI Agent** repository for production deployment on **Railway**.

---

## Changes Completed

### 1. Database Driver Normalization
- Updated [`app/db/database.py`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/db/database.py):
  - Automatically transforms Railway `postgres://` or `postgresql://` connection strings to `postgresql+psycopg://` to transparently select the modern `psycopg` (v3) driver without requiring manual URL editing.

### 2. Platform-Independent Document Storage
- Updated [`app/documents/invoice_pdf.py`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/invoice_pdf.py) & [`app/documents/sales_pptx.py`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/sales_pptx.py):
  - Dynamic resolution of document directories (`invoices`, `reports`) from `settings.local_document_dir`.
  - Platform-independent `pathlib.Path` objects and safe directory creation (`mkdir(parents=True, exist_ok=True)`).

### 3. Railway Manifests & Configuration
- Created [`railway.toml`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/railway.toml):
  - Configured Nixpacks builder with `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`.
  - Set liveness healthcheck path to `/health`.
- Created [`Procfile`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/Procfile):
  - Defined web process entry point `web: uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`.
- Updated [`.env.example`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/.env.example):
  - Added documentation for Railway `DATABASE_URL` format and Railway runtime `PORT` environment variable injection.

### 4. Unit Test Suite
- Created [`tests/test_railway_config.py`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/tests/test_railway_config.py):
  - Verifies Railway `postgres://` and `postgresql://` URL driver transformation to `postgresql+psycopg://`.
  - Verifies `PORT` environment setting override.
  - Verifies `APP_ENV=production` strict validation rules (`DEBUG=false`).
  - Verifies platform-independent document storage path resolution.
  - Verifies `/health` liveness probe.

### 5. Documentation
- Updated [`README.md`](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md):
  - Added **Railway Deployment (Phase 13A.6)** section detailing GitHub integration, PostgreSQL provisioning, environment variables, explicit Alembic migration workflow (`railway run alembic upgrade head`), and health monitoring endpoints (`/health`, `/ready`, `/docs`).

---

## Verification Summary

| Component | Status | Verified Details |
| :--- | :--- | :--- |
| **PORT & HOST Handling** | ✅ **PASSED** | Binds to `0.0.0.0`, reads Railway `$PORT` at runtime. |
| **Database URL Transformation** | ✅ **PASSED** | Converts `postgres://` -> `postgresql+psycopg://`. |
| **Alembic Migration Policy** | ✅ **PASSED** | Schema migrations remain explicit (`railway run alembic upgrade head`). |
| **Health Monitoring** | ✅ **PASSED** | `/health` is liveness probe; `/ready` verifies DB connectivity. |
| **Telegram Polling Decoupling** | ✅ **PASSED** | FastAPI runs as clean web process; Telegram bot remains decoupled. |
| **Security Audit** | ✅ **PASSED** | `.env` untracked, zero hardcoded secrets in manifests or docs. |
| **Unit Test Suite** | ✅ **PASSED** | 155 passed, 2 skipped. |

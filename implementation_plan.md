# Implementation Plan — Phase 13A.6: Railway Deployment Preparation

Prepare the existing Kirana AI Agent codebase for production deployment on **Railway**. This phase configures environment-driven runtime settings (`PORT`, `HOST`), standardizes PostgreSQL database URL handling (`postgres://` / `postgresql://` -> `postgresql+psycopg://`), defines Railway configuration manifests (`railway.toml`, `Procfile`), enforces platform-independent document storage paths, and preserves explicit database migrations (`alembic upgrade head`) and liveness monitoring (`/health`).

---

## User Review Required

> [!IMPORTANT]
> 1. **Railway Service Architecture**: The primary Railway application service runs FastAPI (`uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`). Telegram bot polling remains a separate entry point (`python run_bot.py`) and is not auto-started inside the web service.
> 2. **Explicit Database Migrations**: Migrations are **NOT** automatically executed during FastAPI startup. Migrations must be run explicitly via `railway run alembic upgrade head` (or connected terminal execution).
> 3. **Database Driver Transformation**: Railway provides `DATABASE_URL` in `postgres://` or `postgresql://` format. The application database layer automatically normalizes this string to `postgresql+psycopg://` to transparently use the `psycopg` (v3) driver.
> 4. **No Docker / No Redis / No Webhooks / No Cloud Storage**: Docker, Redis, Celery, Telegram webhooks, and S3/Blob storage remain strictly out of scope for Phase 13A.6.

---

## Open Questions

None. Railway environment and configuration requirements are fully specified.

---

## Proposed Changes

### Core Engine & Database Layer

#### [MODIFY] [app/db/database.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/db/database.py)
- Normalize `postgres://` and `postgresql://` URLs in `_configure_engine` to `postgresql+psycopg://` to support Railway default connection strings cleanly.

#### [MODIFY] [app/documents/sales_pptx.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/sales_pptx.py)
#### [MODIFY] [app/documents/invoice_pdf.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/invoice_pdf.py)
- Dynamic resolution of document directories (`invoices`, `reports`) from `settings.local_document_dir` with cross-platform `pathlib.Path` handling and safe `mkdir(parents=True, exist_ok=True)` directory creation.

---

### Deployment Manifests & Configuration

#### [NEW] [railway.toml](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/railway.toml)
- Define Nixpacks build and deployment configuration:
  - `startCommand = "uvicorn app.api.main:app --host 0.0.0.0 --port $PORT"`
  - `healthcheckPath = "/health"`
  - `healthcheckTimeout = 100`

#### [NEW] [Procfile](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/Procfile)
- Define process entry point:
  `web: uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`

#### [MODIFY] [.env.example](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/.env.example)
- Add Railway deployment documentation comments for `PORT` and PostgreSQL connection strings.

---

### Documentation & Verification Suite

#### [NEW] [tests/test_railway_config.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/tests/test_railway_config.py)
- Unit test suite verifying:
  - Database URL normalization for Railway format (`postgres://...` -> `postgresql+psycopg://...`).
  - Production environment validation (`APP_ENV=production`, `DEBUG=false`).
  - `PORT` environment setting override.
  - Platform-independent document storage path generation.
  - Health check endpoint `/health` liveness.

#### [MODIFY] [README.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md)
- Add **Railway Deployment (Phase 13A.6)** section detailing:
  - GitHub repository connection & Railway project setup.
  - Railway PostgreSQL provisioning & `DATABASE_URL` linking.
  - Required environment variables (`APP_ENV`, `LLM_PROVIDER`, `OPENROUTER_API_KEY`, etc.).
  - Explicit Alembic migration workflow (`railway run alembic upgrade head`).
  - Monitoring `/health` and `/ready` endpoints.

---

## Verification Plan

### Automated Tests
1. Run full test suite:
   ```powershell
   pytest -v
   ```
2. Verify all existing tests pass alongside new `tests/test_railway_config.py` unit tests (target: 154+ passed).

### Manual Verification
1. Validate `railway.toml` syntax and `Procfile` presence.
2. Confirm `.env` remains untracked and uncommitted.
3. Check `git status` for clean git diff.

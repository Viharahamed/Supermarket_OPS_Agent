# 🏪 Kirana AI Agent

A production-grade, conversational Kirana / Supermarket Store AI Agent built for Indian retail operations. Operating with local LLMs (via Ollama `qwen3:8b` or `qwen3:1.7b`), fixed-point financial GST tax arithmetic (`decimal.Decimal`), atomic SQLite transactions, and multi-turn draft billing.

---

## 🚀 Quick Start Guide

### 1. Installation & Environment Setup

Clone the repository and install the dependencies:

```powershell
# Create & activate virtual environment (optional)
python -m venv venv
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

Create your `.env` file from `.env.example`:

```env
# Selected Provider ('ollama' or 'openrouter')
LLM_PROVIDER=ollama

# Ollama Settings (Local Development)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b

# OpenRouter Settings (Production Cloud)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=qwen/qwen-2.5-72b-instruct

DATABASE_URL=sqlite:///./data/kirana.db
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
LOG_LEVEL=INFO
```

---

## 🤖 LLM Provider Configuration

The Kirana AI Agent features a production-grade provider abstraction layer (`app/llm/`). You can seamlessly switch LLM backends without altering business logic, database entities, or Telegram code:

- **Local Ollama Development (Default)**:
  ```env
  LLM_PROVIDER=ollama
  OLLAMA_BASE_URL=http://localhost:11434
  OLLAMA_MODEL=qwen3:1.7b
  ```
- **Production OpenRouter Cloud**:
  ```env
  LLM_PROVIDER=openrouter
  OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
  OPENROUTER_API_KEY=your_actual_api_key_here
  OPENROUTER_MODEL=qwen/qwen-2.5-72b-instruct
  ```

The agent harness automatically instantiates the configured provider via `get_llm_provider()`. If an unsupported provider name or missing OpenRouter API key is specified, the system fails cleanly with a structured configuration exception.

---

### 2. Start Local Ollama AI Engine

Ensure local Ollama is running and has your target model pulled:

```powershell
# Start Ollama service (if not already running)
ollama serve

# Pull model (if needed)
ollama pull qwen3:1.7b
```

---

### 3. Seed Realistic Kirana Demo Data

Populate the database with sample products (Atta, Oil, Maggi, Butter, Salt, Sugar, Toor Dal, Soap, Tea) and Khata customers:

```powershell
python seed_data.py
```

---

### 4. Run the Telegram Bot

Run the Telegram bot runner:

```powershell
python run_bot.py
```

#### Commands Available in Telegram:
- `/start` — Onboarding overview & feature introduction
- `/help` — Full query guide & reference
- `/new` — Reset conversation context *(Store products, stock, bills, and Khata records remain 100% safe!)*

#### Natural Language Telegram Queries:
- **Inventory Check**: `"How much Maggi is left?"`
- **Receive Stock**: `"Add 50 packets of Maggi, cost 12, MRP 14"`
- **Draft Billing**: `"Make a bill for 2 sugar and 4 Maggi"`
- **Edit Bill**: `"Remove Maggi from the bill"`
- **Khata Payments**: `"Ramesh paid 300"`
- **Sales Analytics**: `"What are today's sales?"`
- **PDF Invoice Generation**: `"Generate PDF invoice for bill 1"`
- **PPTX Sales Presentation**: `"Generate sales analysis deck for this week"`

---

### 5. Run Interactive CLI Mode (Alternative)

If you prefer testing directly in terminal:

```powershell
python cli.py
```

---

## 📄 Artifact & Document Generation (Phase 13)

The Kirana AI Agent generates real, production-ready document artifacts:

1. **GST Tax Invoice PDFs (`generated/invoices/`)**:
   - Built using **ReportLab** from immutable historical bill & bill-item snapshots.
   - Includes store branding, customer details, HSN codes, quantity/unit prices, item CGST + SGST tax splits, grand totals, and terms.
2. **8-Slide Sales Analysis PPTX Decks (`generated/reports/`)**:
   - Built using **python-pptx** and headless **Matplotlib** charts.
   - Incorporates real sales metrics, daily sales bar chart, payment method breakdown pie chart, top product revenue bar chart, GST tax breakdown, and inventory health metrics.
3. **Telegram Document Attachment Delivery**:
   - Document tools automatically deliver `.pdf` and `.pptx` files directly to Telegram chats via native Telegram document messages (`reply_document`).

---

## 🧪 Running Automated Tests

Run the complete pytest suite (90+ unit, integration, hardening, document generation, agent evaluation, and Telegram bot tests):

```powershell
# Run all tests
pytest -v

# Run document generation tests specifically
pytest tests/test_documents.py -v

# Run Telegram bot unit tests specifically
pytest tests/test_telegram_bot.py -v
```

---

## 🏗️ Architecture & Features

- **Decoupled Architecture**: Strictly separates natural language understanding (Ollama) from business validation (Python Service Layer) and database storage (SQLite + SQLAlchemy 2.x).
- **Financial Precision**: All monetary amounts, prices, taxes, and stock quantities use `decimal.Decimal` fixed-point arithmetic (`ROUND_HALF_UP`).
- **Stock Safety & Idempotency**: Stock decrements occur in atomic database transactions during `finalize_bill` with idempotency key protection against duplicate commands.
- **Telegram HTML & Document Delivery**: Automatic HTML escaping, formatting (`<b>`, `<i>`, `<code>`, `₹`), long message splitting (>4096 chars), and native file attachment delivery.

---

## ⚙️ Production Configuration (Phase 13A.2)

The application uses a single, centralized, typed configuration system (`app/config.py`) powered by `pydantic-settings`.

### Setup & Usage
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configure required environment variables in `.env`.
3. **LLM Provider Selection**:
   - Local Ollama: Set `LLM_PROVIDER=ollama`.
   - Cloud OpenRouter: Set `LLM_PROVIDER=openrouter` and supply `OPENROUTER_API_KEY`.
4. **Environment Modes (`APP_ENV`)**:
   - `development`: Allows local SQLite and Ollama defaults with `DEBUG=true`.
   - `test`: Used during pytest executions with isolated test settings.
   - `production`: Strictly enforces `DEBUG=false` and requires active provider secrets.
5. **Security Rules**:
   - `.env` is ignored by git and must never be committed.
   - API keys and tokens are automatically masked in log outputs and object string representations.

---

## 🗄️ Database Configuration (Phase 13A.3)

The application supports both **SQLite** for local development/testing and **PostgreSQL** for production deployments via SQLAlchemy 2.x and the `psycopg` 3.x driver.

### Database Selection via `DATABASE_URL`
- **Development (SQLite)**:
  ```env
  DATABASE_URL=sqlite:///./data/kirana.db
  ```
  Automatically enables SQLite-specific connection parameters (`check_same_thread=False`) and connection pragmas (`PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`).

- **Production (PostgreSQL)**:
  ```env
  DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/kirana
  ```
  Uses the modern `psycopg` (v3) driver and configures production connection pooling.

### Connection Pool Configuration (PostgreSQL)
- `DB_POOL_SIZE`: Base pool connection count (default: `5`).
- `DB_MAX_OVERFLOW`: Maximum temporary overflow connections (default: `10`).
- `DB_POOL_TIMEOUT`: Seconds to wait before timing out on pool exhaustion (default: `30`).
- `DB_POOL_RECYCLE`: Connection recycle interval in seconds (default: `1800`).
- `DB_POOL_PRE_PING`: Health check connections before checkout (default: `true`).

---

## 🗄️ Database Initialization (Phase 13A.4)

Database schema initialization is explicitly managed via `Base.metadata.create_all()` through `scripts/init_db.py`.

### Initialization Commands
- **Initialize Database Schema (PostgreSQL or SQLite)**:
  ```bash
  python scripts/init_db.py
  ```

> [!NOTE]
> `init_db.py` dynamically sources `DATABASE_URL` from `app.config.get_settings().database_url` (or `POSTGRES_TEST_URL` during testing). Database initialization is an explicit operation and is not automatically executed on application startup.

---

## ⚡ FastAPI Application Layer (Phase 13A.5)

The Kirana AI Agent includes a production HTTP application layer built on **FastAPI** and **Uvicorn**.

### Running the API Server

Start the local Uvicorn development server:

```powershell
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints & Monitoring

- **`GET /health`** (Process Liveness Probe):
  - Returns HTTP 200 `{"status": "ok"}` without external or database dependencies.
  - Used by container platforms to verify application process liveness.
- **`GET /ready`** (Database Readiness Probe):
  - Executes a lightweight `SELECT 1` query via `get_db_context()`.
  - Returns HTTP 200 `{"status": "ready", "database": "connected"}` when database connectivity is healthy.
  - Returns HTTP 503 `{"status": "not_ready"}` if database is unreachable (without leaking internal exception messages or connection strings).
- **`GET /docs` & `GET /openapi.json`**:
  - Interactive OpenAPI / Swagger UI documentation and API schema specification.

### Security & Middleware
- **CORS Support**: Configured dynamically via `CORS_ORIGINS` in `app/config.py`.
- **Credential Masking**: Health and documentation endpoints are isolated from internal secrets and database credentials.

---

## 🚂 Railway Deployment (Phase 13A.6)

The Kirana AI Agent is prepared for production deployment on **Railway**.

### Deployment Architecture

- **Web Application Service**: Runs FastAPI (`uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`) using standard Nixpacks build context (`railway.toml` / `Procfile`).
- **Railway PostgreSQL Service**: Production relational database providing `DATABASE_URL` (`postgres://...` or `postgresql://...`). The app automatically standardizes connection strings to `postgresql+psycopg://`.

### Railway Deployment Workflow

1. **Push Repository to GitHub**: Connect your repository to Railway.
2. **Create Railway Project**: Add a new web service pointing to the repository.
3. **Provision Railway PostgreSQL**: Add a PostgreSQL database service in the Railway project.
4. **Link Environment Variables**:
   - `APP_ENV`: `production`
   - `DEBUG`: `false`
   - `LLM_PROVIDER`: `openrouter`
   - `OPENROUTER_API_KEY`: `your_actual_openrouter_key`
   - `DATABASE_URL`: `${{ Postgres.DATABASE_URL }}`
   - `TELEGRAM_BOT_TOKEN`: `your_telegram_bot_token`
5. **Run Alembic Schema Migrations Explicitly**:
   Execute migrations against Railway PostgreSQL:
   ```bash
   railway run alembic upgrade head
   ```
6. **Verify Endpoints**:
   - Process Liveness Probe: `GET /health`
   - Database Readiness Probe: `GET /ready`
   - OpenAPI Documentation: `GET /docs`

> [!IMPORTANT]
> Database schema migrations are **explicit** operations and are **not** auto-executed during FastAPI startup. Telegram polling remains decoupled from the web application process.

---

## 🛑 Architectural Note: Redis Evaluation (Phase 13A.7)

During Phase 13A.7, a formal architectural evaluation concluded that **Redis is intentionally NOT part of the current production stack**.

- **PostgreSQL is Authoritative**: PostgreSQL 16+ provides complete ACID transaction atomicity, row-level stock locks, and session/preference durability.
- **Minimal Operational Overhead**: Query response times for inventory and sessions are `< 2ms`, rendering caching unnecessary for current retail operational volumes.
- **Future Reconsideration**: Redis may be reconsidered if specific scaling requirements emerge (e.g. 5+ API replicas, heavy async worker queues, or distributed rate limiting).

For full details, see the Architectural Decision Record: [docs/architecture/redis-decision.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/docs/architecture/redis-decision.md).

---

## 📂 Document Storage & Persistence (Phase 13B.2)

The Kirana AI Agent uses a clean document storage abstraction (`app/storage/`) to manage PDF invoices, PPTX presentation decks, and report artifacts.

### 🏗️ Conceptual Architecture

```
                 Document Generators (PDF / PPTX)
                                |
                                v
                         Artifact Result
                                |
                                v
                     DocumentStorage Interface
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
      Local Development                     Railway Production
   (LocalStorageBackend)                  (LocalStorageBackend)
             |                                     |
             v                                     v
   Local Filesystem Path               Persistent Railway Volume Mount
   (LOCAL_DOCUMENT_DIR=generated)      (LOCAL_DOCUMENT_DIR=/app/data/generated)
```

### ⚙️ Configuration & Environment

Storage configuration is managed via `app/config.py`:

- **Development (`DOCUMENT_STORAGE=local`)**:
  ```env
  DOCUMENT_STORAGE=local
  LOCAL_DOCUMENT_DIR=generated
  ```
  Writes generated artifacts to the local `./generated/` directory.

- **Railway Production (`DOCUMENT_STORAGE=local`)**:
  ```env
  DOCUMENT_STORAGE=local
  LOCAL_DOCUMENT_DIR=/app/data/generated
  ```
  *(Note: `DOCUMENT_STORAGE=local` indicates a filesystem-backed implementation; persistence in Railway production is provided by the mounted Railway Volume).*

### 🚂 Railway Volume Setup Guide

1. Open your Railway Project Dashboard.
2. Select your Kirana AI Agent service.
3. Click **Add Volume** under service settings.
4. Mount the volume to path: `/app/data/generated`.
5. Set environment variable `LOCAL_DOCUMENT_DIR=/app/data/generated`.
6. Generated PDFs and PPTX presentations will automatically survive service restarts and redeployments.

### 🔒 Storage Security & Integrity

- **Path Traversal Prevention**: Storage backends strictly reject absolute paths, null bytes, `../`, and `..\` relative sequences (`InvalidStoragePathError`).
- **Binary Support**: Native binary handling (`.pdf`, `.pptx`, `.png`).
- **Database vs. Storage Separation**: PostgreSQL stores authoritative business data (bills, items, inventory). Binary files are stored exclusively in document storage.
- **Future Object Storage**: S3/GCS object storage backends can be added behind the `DocumentStorage` interface without modifying generators, tools, or Telegram handlers.

---

## 🔐 Authentication & Multi-Tenancy (Phase 14)

The Kirana AI Agent supports production-grade multi-tenancy and store isolation. Multiple retail stores and users operate on a single shared platform with guaranteed data isolation.

### 🔑 Security Principles & Tenant Isolation
1. **Single Canonical Tenant Identifier**: `store_id` (foreign key to `stores.id`).
2. **Untrusted LLM Arguments**: `store_id` is NEVER accepted or trusted from LLM function call arguments. It is strictly injected from the application's authenticated execution context (`AuthenticatedPrincipal`).
3. **Database-Level Isolation**: All business domain tables (`products`, `stock_movements`, `customers`, `bills`, `khata_transactions`, `owner_preferences`, `agent_sessions`) feature mandatory `store_id` foreign keys and store-scoped database indexes.
4. **Isolated Document Artifacts**: PDFs and PPTX files are partitioned into store-isolated directories (`stores/<store_id>/invoices/` and `stores/<store_id>/reports/`).
5. **Session Isolation**: Chat session histories are composite-keyed by `(store_id, user_id)` so Store A can never access Store B's agent interactions.

### 👤 Identity & Roles
- **Identity Provider**: Users authenticate via Telegram User ID mapping to database `users` records.
- **Roles**:
  - `OWNER`: Full store management rights (inventory, billing, reporting, preferences).
  - `OPERATOR`: Store operational rights (billing, inventory lookups, customer Khata).
- **Auto-Bootstrapping**: Fresh database installations auto-bootstrap Store #1 and User #1 upon first execution to maintain single-store developer convenience.
- **Unauthorized Access**: Unregistered Telegram user IDs are rejected with clean warning responses.

---

## 🚀 Telegram Webhook & Production Deployment (Phase 15)

The Kirana AI Agent supports both local polling for development and secure HTTPS webhook processing for production Railway deployments.

### ⚙️ Operating Modes (`TELEGRAM_MODE`)
- **Local Development (`TELEGRAM_MODE=polling`)**:
  - Run bot runner: `python run_bot.py`.
  - Uses standard long polling loop. Requires no public base URL or webhook secret.
- **Production Webhook (`TELEGRAM_MODE=webhook`)**:
  - Hosted inside FastAPI application (`POST /telegram/webhook`).
  - Started via `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`.
  - Managed by FastAPI application lifespan (`lifespan`).
  - Requires `TELEGRAM_WEBHOOK_SECRET` and HTTPS `PUBLIC_BASE_URL`.

### 🛡️ Webhook Security & Architecture
1. **Secret Token Header Validation**: Every incoming update must include header `X-Telegram-Bot-Api-Secret-Token` matching `TELEGRAM_WEBHOOK_SECRET`. Unauthenticated requests are rejected with HTTP 403.
2. **Credential Masking**: Bot token is never part of the URL path (`POST /telegram/webhook`). Webhook secret is masked in logs and representation outputs.
3. **No Duplicate Execution**: Startup fast-fails if polling is launched when `TELEGRAM_MODE=webhook`.

### 📋 Production Environment Variables

| Variable Name | Production Value Example | Purpose |
|---|---|---|
| `APP_ENV` | `production` | Enables production validation rules |
| `DEBUG` | `false` | Disables debug mode and stack traces |
| `LLM_PROVIDER` | `openrouter` | Selects OpenRouter cloud backend |
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | OpenRouter API Key |
| `DATABASE_URL` | `postgresql+psycopg://...` | Railway PostgreSQL database URL |
| `TELEGRAM_BOT_TOKEN` | `123456789:ABC...` | Telegram Bot API token |
| `TELEGRAM_MODE` | `webhook` | Enables production webhook mode |
| `TELEGRAM_WEBHOOK_SECRET` | `secret_token_abc123` | Telegram secret header validation token |
| `PUBLIC_BASE_URL` | `https://kirana-bot.up.railway.app` | Public HTTPS URL of deployed service |
| `DOCUMENT_STORAGE` | `local` | Filesystem storage backend |
| `LOCAL_DOCUMENT_DIR` | `/app/data/generated` | Persistent Railway Volume mount path |
| `TIMEZONE` | `Asia/Kolkata` | Application timezone |

### 🛠️ Production Deployment Runbook

1. **Deploy Code & Provision Railway Services**:
   - Push repository to private GitHub and link to Railway project.
   - Provision Railway PostgreSQL database service and set `DATABASE_URL`.
   - Add Railway Volume mounted to `/app/data/generated` and set `LOCAL_DOCUMENT_DIR=/app/data/generated`.
2. **Configure Production Environment Variables**:
   - Set `APP_ENV=production`, `DEBUG=false`, `TELEGRAM_MODE=webhook`, `TELEGRAM_WEBHOOK_SECRET`, `PUBLIC_BASE_URL`.
3. **Initialize Database Tables**:
   Run the explicit initialization script in the Railway Web Console:
   ```bash
   python scripts/init_db.py
   ```
4. **Register Telegram Webhook**:
   Run the controlled registration setup script:
   ```bash
   python scripts/register_webhook.py
   ```
5. **Verify Endpoints & Health**:
   - Liveness Probe: `GET /health` (HTTP 200)
   - Readiness Probe: `GET /ready` (HTTP 200)
   - Send test message on Telegram and verify update processing, DB updates, and PDF/PPTX attachment delivery.









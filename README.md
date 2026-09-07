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

## 🔄 Database Migrations (Phase 13A.4)

Database schema evolution is managed via **Alembic**.

### Migration Commands
- **Upgrade Database Schema to Latest Revision**:
  ```bash
  alembic upgrade head
  ```
- **Check Current Migration Revision**:
  ```bash
  alembic current
  ```
- **View Migration History**:
  ```bash
  alembic history
  ```
- **Downgrade Schema (Development/Testing only)**:
  ```bash
  alembic downgrade base
  ```

> [!NOTE]
> Alembic dynamically sources `DATABASE_URL` from `app.config.get_settings().database_url` (or `POSTGRES_TEST_URL` during testing). Never hardcode credentials in `alembic.ini`.

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





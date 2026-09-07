# 🏪 Kirana AI Agent — Store Operations Assistant

A production-grade, conversational AI Store Operations Agent designed specifically for Indian supermarket and Kirana store retail operations. The system automates inventory management, GST-compliant draft and final billing, customer Khata ledger tracking, daily sales reporting, and document generation via Telegram.

TELEGRAM BOT LINK : t.me/kirana_ai_assistant_bot. 
---

## 1. What the System Does

- **Inventory & Stock Tracking**: Real-time product lookup, low stock alerts, stock receiving, cost/MRP updates, and audit movement logs.
- **GST Billing Engine**: Fixed-point decimal arithmetic for CGST, SGST, and IGST tax calculations, multi-item draft creation, bill edits, and immutable finalization.
- **Khata Customer Ledger**: Manages customer credit balances, payments, credit limits, and ledger histories.
- **Analytics & Daily Reports**: Daily sales, tax collection summaries, cash vs UPI breakdowns, top product metrics, and weekly sales analysis.
- **Document Generation**: Produces downloadable GST Invoice PDFs (ReportLab) and Weekly Sales Analytics PowerPoint presentations (python-pptx/matplotlib).

---

## 2. System Architecture

```
Telegram (Polling / Webhook)
           ↓
   FastAPI HTTP Layer
           ↓
    Agent Control Loop (Observe -> Reason -> Act -> Observe)
           ↓
    Tool Registry Allowlist (Typed & Schema-Validated)
           ↓
   Business Service Layer (Rules & Multi-Tenant Authorization)
           ↓
 Database (SQLite Dev / PostgreSQL Prod via SQLAlchemy)
```

---

## 3. LLM Architecture

- **Development Backend**: Local [Ollama](https://ollama.ai/) (`qwen3:1.7b` or `qwen3:8b`). Zero cloud API costs and offline testing.
- **Production Backend**: [OpenRouter API](https://openrouter.ai/) (`qwen/qwen-2.5-72b-instruct`). Provider abstraction layer (`app/llm/`) allows seamless switching via `LLM_PROVIDER`.

---

## 4. Agent Control Loop

The custom agent harness operates an iterative decision loop without third-party frameworks:

```
User Input → OBSERVE Context → REASON (LLM JSON Action) → ACT (Tool Execution) → OBSERVE Result → Final Response
```

---

## 5. Tool Design & Safety Rules

- **Explicit Allowlist**: Tools are registered in a strictly defined `ToolRegistry`.
- **Typed Inputs**: Pydantic schemas enforce type safety on tool arguments.
- **Service Isolation**: LLM has zero direct database access; all modifications pass through business services enforcing store context (`store_id`).
- **Authorization**: Execution context (`ToolExecutionContext`) verifies `OWNER` vs `OPERATOR` permissions.

---

## 6. Business & Financial Safety

- **Oversell Prevention**: Stock cannot drop below zero during bill finalization.
- **Atomic Billing**: Stock decrements occur atomically upon finalization within a database transaction.
- **GST Correctness**: Calculated using exact `Decimal` arithmetic; rounded deterministically.
- **Finalized Bill Immutability**: Finalized bills cannot be edited, deleted, or double-decremented (idempotent retry safety).
- **Tenant Isolation**: Multi-tenant database design ensures Store A cannot access Store B products, bills, Khata ledgers, or documents.

---

## 7. Persistent Memory & State

- **Conversational Session State**: Short-term conversation history stored per user in memory/file (`load_session_history`).
- **Persistent Owner Preferences**: Long-term store preferences (e.g. default payment method, default supplier brand) saved permanently in database `owner_preferences` table.
- **Session Reset (`/new`)**: Resets user conversation history while leaving stock, bills, Khata balances, and preferences 100% intact.

---

## 8. Generated Document Artifacts

- **GST Invoice PDF**: Formatted with store header, customer details, HSN breakdown, tax summary, and signature line.
- **Weekly Sales Analysis PPTX**: Slide presentation containing sales trend charts, top selling products, and payment breakdowns.

---

## 9. Dual Telegram Runtime Modes

- **Development (`TELEGRAM_MODE=polling`)**: Long-polling background task via `python run_bot.py`.
- **Production (`TELEGRAM_MODE=webhook`)**: FastAPI endpoint `POST /telegram/webhook` with `X-Telegram-Bot-Api-Secret-Token` validation.

---

## 10. Automated Testing & Quality

- **Test Suite**: 200+ comprehensive automated tests covering unit, integration, and Phase 16 E2E scenarios.
- **CI Pipeline**: GitHub Actions workflow (`.github/workflows/ci.yml`) executing tests under isolated in-memory SQLite setup on every push and pull request.

---

## 🛠️ Quick Start

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database schema explicitly
python scripts/init_db.py

# 3. Seed demo Kirana products and customers
python seed_data.py

# 4. Run local Telegram Bot
python run_bot.py

# 5. Run tests
pytest -q
```

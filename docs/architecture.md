# Kirana AI Agent — Technical Architecture Specification

## 1. Executive Summary & Core Architectural Principles

The **Kirana AI Agent** is a production-grade, conversational store management system engineered specifically for Indian kirana and supermarket retail operations.

### Core Architectural Principle: Strict Separation of Concerns
1. **LLM Layer (Ollama / OpenRouter)**:
   - Responsible strictly for **Intent Understanding**, **Tool Selection**, **Parameter Extraction**, **Ambiguity Clarification**, and **Natural Language Response Synthesis**.
   - The LLM **NEVER** accesses the database directly.
   - The LLM **NEVER** executes arbitrary SQL or shell commands.
   - The LLM **NEVER** performs financial or stock math.

2. **Application & Service Layer (Python 3.12 / FastAPI)**:
   - Responsible for **Business Rule Validation**, **Financial & GST Tax Math (Decimal)**, **Stock Mutation Guards**, **Concurrency Controls**, **Idempotency Enforcement**, and **Multi-Tenant Context Isolation**.
   - Resolves product queries, calculates taxes, and generates document artifacts (PDF/PPTX).

3. **Database & Persistence Layer (PostgreSQL / SQLite via SQLAlchemy 2.x)**:
   - Enforces **Data Integrity**, **ACID Transactions**, **Foreign Key Constraints**, and **Unique Idempotency Keys**.
   - Initialized explicitly via `python scripts/init_db.py` (`Base.metadata.create_all()`).

---

## 2. Component Architecture Diagram

```
Telegram Client (Polling or Webhook)
                │
                ▼
      FastAPI Webhook Router / Polling Handler
                │
                ▼
        Authentication & Store Identity Layer
   (Maps Telegram ID -> AuthenticatedPrincipal: store_id)
                │
                ▼
       Custom Agent Loop (Observe -> Reason -> Act -> Observe)
                │
                ▼
        Tool Registry & Execution Context
   (Pydantic Schema Validation & Trusted Context Injection)
                │
                ▼
     Business Service Layer (Rules & Financial Decimal Math)
 ┌──────────────┬──────────────┬──────────────┬──────────────┐
 │ Inventory    │ Billing      │ Payments     │ Reporting    │
 │ Service      │ Service      │ & Khata      │ Service      │
 └──────────────┴──────────────┴──────────────┴──────────────┘
                │
                ▼
    SQLAlchemy 2.x ORM / Database (SQLite Dev / PostgreSQL Prod)
```

---

## 3. Detailed Component Specifications

### 3.1 LLM Provider Abstraction
- Defined by `app.llm.provider.LLMProvider` interface.
- Implementations: `OllamaProvider` (local dev) and `OpenRouterProvider` (production cloud).
- Selected dynamically via `LLM_PROVIDER` environment setting.

### 3.2 Custom Agent Control Loop
- Operates a deterministic 4-phase iteration cycle: `OBSERVE` -> `REASON` -> `ACT` -> `OBSERVE`.
- Capped at `AGENT_MAX_ITERATIONS` (default: 8).
- Maintains session memory using `agent_sessions`.

### 3.3 Multi-Tenancy & Security Model
- **Authentication**: `authenticate_telegram_user(telegram_user_id)` resolves the user's active `store_id` and `role` (`OWNER` or `OPERATOR`).
- **Isolation**: Every database query across products, bills, Khata customers, preferences, and reports is strictly filtered by `store_id`.
- **Context Injection**: `ToolExecutionContext` holds the `AuthenticatedPrincipal`. The LLM cannot specify or alter `store_id`.

### 3.4 Dual Telegram Runtime Architecture
- **Development**: Telegram polling runner (`python run_bot.py`).
- **Production**: FastAPI webhook endpoint (`POST /telegram/webhook`) with `X-Telegram-Bot-Api-Secret-Token` validation and lifespan management.

### 3.5 Document Generation & Storage Abstraction
- **PDF Invoices**: Generated via ReportLab (`app/documents/pdf_generator.py`) with HSN tax summaries.
- **Weekly PPTX Analysis**: Generated via python-pptx and Matplotlib (`app/documents/pptx_generator.py`).
- **Storage**: Abbreviated path handling via `app/storage/document_storage.py`.

### 3.6 Error Handling & Log Correlation
- Domain exceptions inherit from `KiranaException` / `ApplicationError`.
- Unhandled exceptions mapped to friendly user responses in Telegram handlers without leaking stack traces.
- Lightweight correlation tracking using `contextvars.ContextVar` (`[corr_id=...]`).
- Automatic secret masking (`SecretMaskingFormatter`) redacting bot tokens, API keys, and database passwords.

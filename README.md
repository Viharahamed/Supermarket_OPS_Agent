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


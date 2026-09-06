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
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b
DATABASE_URL=sqlite:///./data/kirana.db
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
LOG_LEVEL=INFO
```

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

---

### 5. Run Interactive CLI Mode (Alternative)

If you prefer testing directly in terminal:

```powershell
python cli.py
```

---

## 🧪 Running Automated Tests

Run the complete pytest suite (78+ unit, integration, hardening, agent evaluation, and Telegram bot tests):

```powershell
# Run all tests
pytest -v

# Run Telegram bot unit tests specifically
pytest tests/test_telegram_bot.py -v
```

---

## 🏗️ Architecture & Features

- **Decoupled Architecture**: Strictly separates natural language understanding (Ollama) from business validation (Python Service Layer) and database storage (SQLite + SQLAlchemy 2.x).
- **Financial Precision**: All monetary amounts, prices, taxes, and stock quantities use `decimal.Decimal` fixed-point arithmetic (`ROUND_HALF_UP`).
- **Stock Safety & Idempotency**: Stock decrements occur in atomic database transactions during `finalize_bill` with idempotency key protection against duplicate commands.
- **Telegram HTML Safety**: Automatic HTML escaping, formatting (`<b>`, `<i>`, `<code>`, `₹`), and long message splitting (>4096 chars).

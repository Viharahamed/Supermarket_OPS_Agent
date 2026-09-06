# Kirana AI Agent Architecture Specification

## 1. Executive Summary & Core Architectural Principles

The **Kirana AI Agent** is a production-grade, conversational store management system engineered specifically for Indian kirana / supermarket operations. 

### Core Architectural Principle: Strict Separation of Concerns
1. **LLM Layer (Ollama / Qwen3 8B)**:
   - Responsible strictly for **Intent Understanding**, **Tool Selection**, **Parameter Extraction**, **Ambiguity Clarification Request**, and **Natural Language Response Synthesis**.
   - The LLM **NEVER** accesses the database directly.
   - The LLM **NEVER** executes arbitrary SQL or raw shell commands.
   - The LLM **NEVER** performs financial or stock math.

2. **Application / Service Layer (Python 3.12)**:
   - Responsible for **Business Rule Validation**, **Financial & Tax Math (Decimal)**, **Stock Mutation Guards**, **Concurrency Controls**, **Idempotency Enforcement**, and **Transactional Commit/Rollback**.
   - Handles ambiguity detection (e.g., matching partial product queries like "atta" to multiple catalog entries and prompting clarification).

3. **Database Layer (SQLite + SQLAlchemy 2.x)**:
   - Enforces **Data Integrity**, **ACID Transactions**, **Foreign Key Constraints**, and **Unique Idempotency Keys**.

---

## 2. Requirements & Design Decisions Analysis

| Requirement Area | Challenge / Risk | Resolved Design Decision |
| :--- | :--- | :--- |
| **Financial Safety** | Floating-point inaccuracies in prices/taxes | All monetary and tax calculations use `decimal.Decimal` with fixed-point rounding rules (`ROUND_HALF_UP` to 2 decimal places). |
| **Stock Safety** | Concurrent finalization & overselling | Stock decrements occur strictly within isolated database transactions during `finalize_bill`. Negative stock is rejected at database and service layer. |
| **Draft Bill Multi-Turn Editing** | Premature stock allocation | Editing draft bills (`add_item`, `remove_item`, `update_quantity`) operates solely on draft entities and **does NOT decrement stock**. Stock is reserved/decremented only upon `finalize_bill`. |
| **Telegram Network Retries** | Duplicate finalizations / ledger corruptions | `finalize_bill` and `record_payment` require explicit `idempotency_key`. Redelivery returns existing finalized bill without re-executing state mutation. |
| **Persistent vs Session State** | Loss of owner preferences on `/new` reset | Session conversation history (`agent_sessions`) is cleared on `/new`, but `owner_preferences` persist in SQLite. System prompt injects active preferences on every loop. |
| **Local Model Constraints** | Ollama Qwen3 8B tool calling capabilities | Built custom agent loop supporting native function calls, structured Pydantic schemas, explicit tool error responses, and fallback handling for missing tool parameters. |

---

## 3. Component Architecture & Data Flow

```
+-----------------------------------------------------------------------+
|                             Telegram UI                               |
|                     (python-telegram-bot async)                       |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                         Custom Agent Loop                             |
|               (Observe -> Reason -> Act -> Observe)                   |
|                                                                       |
|  1. Load Session History & Preferences                                |
|  2. Construct Context & System Prompt                                 |
|  3. Dispatch to Local Ollama API (qwen3:8b)                           |
+-----------------------------------------------------------------------+
                        |                      ^
         Tool Call Req  |                      | Tool Result Payload
                        v                      |
+-----------------------------------------------------------------------+
|                             Tool Registry                             |
|         (Pydantic Schema Validation & Tool Router Adapter)            |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                           Business Services                           |
|  [InventoryService] [GSTService] [BillingService] [KhataService]      |
|           [ReportingService] [PreferenceService]                      |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                    SQLAlchemy 2.x ORM / Repositories                  |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                         SQLite Database (WAL)                         |
+-----------------------------------------------------------------------+
```

---

## 4. Database Entity Relationship (ER) Schema

### 4.1 Table Definitions

```mermaid
erdiagram
    STORES ||--o{ PRODUCTS : owns
    STORES ||--o{ CUSTOMERS : serves
    STORES ||--o{ BILLS : issues
    PRODUCTS ||--o{ STOCK_MOVEMENTS : tracks
    PRODUCTS ||--o{ BILL_ITEMS : contained_in
    CUSTOMERS ||--o{ BILLS : places
    CUSTOMERS ||--o{ KHATA_TRANSACTIONS : ledger
    BILLS ||--o{ BILL_ITEMS : contains
    BILLS ||--o{ KHATA_TRANSACTIONS : referenced_in

    STORES {
        int id PK
        string name
        string address
        string gstin
        datetime created_at
        datetime updated_at
    }

    PRODUCTS {
        int id PK
        string sku UK
        string name
        string brand
        string category
        string unit
        decimal pack_size
        boolean is_loose
        decimal cost_price
        decimal selling_price
        decimal mrp
        decimal gst_rate
        string hsn_code
        decimal stock_quantity
        decimal reorder_level
        boolean active
        datetime created_at
        datetime updated_at
    }

    STOCK_MOVEMENTS {
        int id PK
        int product_id FK
        string movement_type
        decimal quantity
        decimal stock_after
        string reference_id
        string notes
        datetime created_at
    }

    CUSTOMERS {
        int id PK
        string name
        string phone
        decimal khata_balance
        datetime created_at
        datetime updated_at
    }

    KHATA_TRANSACTIONS {
        int id PK
        int customer_id FK
        int bill_id FK
        string transaction_type
        decimal amount
        decimal balance_after
        string idempotency_key UK
        string notes
        datetime created_at
    }

    BILLS {
        int id PK
        string bill_number UK
        string idempotency_key UK
        string status
        int customer_id FK
        string payment_method
        string payment_status
        decimal subtotal
        decimal taxable_amount
        decimal cgst_amount
        decimal sgst_amount
        decimal tax_total
        decimal discount_amount
        decimal rounding_amount
        decimal grand_total
        datetime created_at
        datetime updated_at
    }

    BILL_ITEMS {
        int id PK
        int bill_id FK
        int product_id FK
        string product_name_snapshot
        decimal quantity
        decimal unit_price
        decimal cost_price
        decimal mrp
        decimal gst_rate
        string hsn_code
        decimal taxable_amount
        decimal cgst
        decimal sgst
        decimal tax_amount
        decimal line_total
        datetime created_at
    }

    OWNER_PREFERENCES {
        string key PK
        string value
        datetime updated_at
    }

    AGENT_SESSIONS {
        int user_id PK
        string history_json
        datetime updated_at
    }
```

---

## 5. Service and Tool Boundary Mapping

```
                 LLM Tool Call Request
                           │
                           ▼
               ┌───────────────────────┐
               │    Tool Registry      │
               └───────────┬───────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
 ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
 │Inventory Tools│ │ Billing Tools │ │  Khata Tools  │
 └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
         │                 │                 │
         ▼                 ▼                 ▼
 ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
 │InventorySvc   │ │ BillingSvc    │ │ KhataSvc      │
 └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │   SQLAlchemy Models   │
               └───────────────────────┘
```

Every tool execution returns a standardized **`ToolResult`**:
```json
{
  "success": true,
  "data": { ... },
  "error_code": null,
  "message": "Operation completed successfully.",
  "details": {}
}
```

---

## 6. Custom Ollama Agent Loop Design

The agent loop executes an iterative **Observe -> Reason -> Act** cycle:

1. **User Input Ingestion**: Receives message from Telegram handler.
2. **Context Enrichment**: Fetches conversation history (`agent_sessions`) and active store preferences (`owner_preferences`).
3. **Prompt Construction**: Formulates system prompt specifying strict operational constraints, output formatting rules, grounded tool access, and current state.
4. **Ollama Invocation**: Sends payload to Ollama (`qwen3:8b`).
5. **Tool Dispatch & Result Feedback**:
   - If model returns `tool_calls`: Parse arguments with Pydantic, execute registered python function against business services, append output as `role: tool` message.
   - Loop back to step 4 (up to `max_iterations = 10`).
6. **Final Output Generation**: Returns natural language summary (and optional document path attachment e.g. PDF invoice or PPTX report) back to Telegram.

---

## 7. Directory Structure Specification

```
kirana-ai-agent/
├── app/
│   ├── agent/
│   │   ├── agent.py          # Primary agent coordinator
│   │   ├── loop.py           # Execution loop implementation
│   │   ├── prompts.py        # System prompt templates
│   │   ├── schemas.py        # Agent state & response structures
│   │   └── tool_registry.py  # Function router & tool metadata
│   ├── db/
│   │   ├── database.py       # Session maker & SQLite connection setup
│   │   ├── models.py         # SQLAlchemy 2.x declarative models
│   │   └── repositories.py   # Data access queries
│   ├── documents/
│   │   ├── charts.py         # Matplotlib visual generation
│   │   ├── invoice_pdf.py    # ReportLab PDF invoice builder
│   │   └── sales_pptx.py     # python-pptx presentation builder
│   ├── services/
│   │   ├── billing_service.py   # Draft & transaction billing logic
│   │   ├── gst_service.py       # Deterministic CGST/SGST tax math
│   │   ├── inventory_service.py # Product stock & movement logic
│   │   ├── khata_service.py     # Customer credit & payment ledger
│   │   ├── preference_service.py# Key-value store configuration
│   │   └── reporting_service.py # Analytics aggregation engine
│   ├── telegram/
│   │   ├── bot.py            # Telegram bot initialization
│   │   └── handlers.py       # Bot command and text handlers
│   ├── tools/
│   │   ├── billing.py        # Tool adapters for billing
│   │   ├── documents.py      # Tool adapters for PDF/PPTX generation
│   │   ├── inventory.py      # Tool adapters for inventory
│   │   ├── khata.py          # Tool adapters for khata
│   │   ├── preferences.py    # Tool adapters for store preferences
│   │   └── reporting.py      # Tool adapters for sales reports
│   ├── config.py             # Settings loading via pydantic-settings / dotenv
│   └── main.py               # Application entrypoint
├── data/
│   └── .gitkeep              # SQLite DB location
├── docs/
│   └── architecture.md       # Architecture Specification
├── generated/
│   ├── invoices/             # Output PDF invoices
│   └── reports/              # Output PPTX reports
├── tests/
│   ├── test_agent_tools.py
│   ├── test_billing.py
│   ├── test_concurrency.py
│   ├── test_gst.py
│   ├── test_idempotency.py
│   ├── test_inventory.py
│   └── test_khata.py
├── requirements.txt
└── run.py

---

## 8. GST & Pricing Engine Specification

### 8.1 Core Formulas & Rules
1. **Intra-State Equal Split**:
   - `cgst_rate = gst_rate / 2`
   - `sgst_rate = gst_rate / 2`
   - `taxable_amount = quantize_money(unit_price * quantity)`
   - `cgst_amount = quantize_money(taxable_amount * (cgst_rate / 100))`
   - `sgst_amount = quantize_money(taxable_amount * (sgst_rate / 100))`
   - `total_tax = cgst_amount + sgst_amount`
   - `line_total = taxable_amount + total_tax`

2. **Rounding Policy**:
   - Explicit `ROUND_HALF_UP` to 2 decimal places (`Decimal("0.01")`). Applied uniformly across all line item calculations and billing totals.

3. **Pricing Rules**:
   - `cost_price >= 0`, `selling_price >= 0`, `mrp >= 0`
   - `selling_price >= cost_price` (rejects selling below cost price via `PriceBelowCostError`)
   - `selling_price <= mrp` (rejects selling above MRP via `PriceAboveMRPError`)

---

## 9. Billing Engine Specification

### 9.1 Bill Lifecycle & Operational Guarantees
1. **Lifecycle States**:
   - `DRAFT` ➔ `FINALIZED`
   - Draft bills are created via `create_draft_bill()`.

2. **Draft Isolation (Stock Safety Invariant)**:
   - Mutations on draft bills (`add_bill_item`, `update_bill_item`, `remove_bill_item`) operate exclusively on draft entities and **never** mutate product stock.

3. **Duplicate Product Handling**:
   - Adding an existing product to a draft bill aggregates quantity on the existing `BillItem` entity rather than creating duplicate line items.

4. **Atomic Finalization & Oversell Protection**:
   - `finalize_bill()` executes within an isolated database transaction.
   - Re-reads and validates current product stock for all items. If any item is insufficient (`stock_quantity < requested`), transaction rolls back immediately raising `InsufficientStockError`, leaving stock and draft bill unchanged.
   - Atomically decrements product stock and records `StockMovement(movement_type="SALE")` for sold items upon successful commit.

5. **Finalized Bill Immutability**:
   - Once a bill transitions to `FINALIZED`, further modifications (`add_bill_item`, `update_bill_item`, `remove_bill_item`) are rejected with `BillAlreadyFinalizedError`.

6. **Idempotency Guarantee**:
   - Calling `finalize_bill()` on an already `FINALIZED` bill returns the existing finalized bill without re-running stock decrements or logging duplicate `SALE` movements.



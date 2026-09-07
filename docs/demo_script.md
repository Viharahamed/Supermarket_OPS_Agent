# 🎥 Kirana AI Agent — Live Demonstration Script (4–5 Minutes)

This demonstration script showcases the core features, business rules, financial safety, document generation, and multi-tenant capabilities of the Kirana AI Agent.

---

## Demonstration Setup
- **Target Time**: 4 to 5 minutes
- **Interface**: Telegram Bot or API Test Harness
- **Environment**: Local Development or Staging Instance

---

## 🎬 14-Step Demonstration Flow

### Step 1: Stock Receiving (Inventory Management)
**User Input**:
> `"50 packets of Maggi came in, cost ₹12, MRP ₹14"`

**Expected System Behavior**:
- Product `"Maggi Noodles 70g"` resolved.
- Current stock increases by 50 units.
- Cost price (₹12.00) and MRP (₹14.00) updated/validated.
- Stock movement recorded as `PURCHASE`.

---

### Step 2: Stock Level Query
**User Input**:
> `"How much Maggi do we have in stock?"`

**Expected System Behavior**:
- Agent executes `get_product_stock` tool.
- Reports updated stock level (e.g., 60 packets available).

---

### Step 3: Multi-Item Draft Bill Creation
**User Input**:
> `"Make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter"`

**Expected System Behavior**:
- Product names resolved from database catalog.
- Draft bill created in status `DRAFT`.
- Items added with grounded database unit prices and GST tax calculations.
- **Stock is NOT decremented during draft status.**

---

### Step 4: Multi-Turn Bill Editing
**User Input**:
> `"Drop the butter, make it 6 Maggi"`

**Expected System Behavior**:
- Amul Butter removed from draft bill.
- Maggi quantity updated from 4 to 6.
- Total bill amount updated.
- Bill status remains `DRAFT`. Stock remains untouched.

---

### Step 5: Finalize Bill with UPI Payment
**User Input**:
> `"Finalize the bill with UPI"`

**Expected System Behavior**:
- Atomic transaction executes.
- Stock decremented atomically (6 Maggi, 2kg Sugar, 1 Atta).
- Payment method recorded as `UPI`.
- Bill status updated to `FINALIZED`. Bill becomes immutable.

---

### Step 6: Attempt Oversell (Stock Safety Guard)
**User Input**:
> `"Make a bill for 100 Aashirvaad atta 5kg and finalize with cash"`

**Expected System Behavior**:
- Transaction rejected with `InsufficientStockError`.
- System notifies user that only 49 packets are in stock.
- Stock is never reduced below zero.

---

### Step 7: Khata Customer Credit Record
**User Input**:
> `"Put ₹500 on Ramesh's credit"`

**Expected System Behavior**:
- Customer Ramesh Kumar resolved/created.
- Ledger credit transaction recorded (+₹500.00).
- Updated balance reported as ₹500.00 credit.

---

### Step 8: Khata Customer Payment Record
**User Input**:
> `"Ramesh paid ₹300 via UPI"`

**Expected System Behavior**:
- Payment transaction recorded (-₹300.00).
- Outstanding Khata balance updated to ₹200.00.

---

### Step 9: Generate GST Invoice PDF Document
**User Input**:
> `"Generate invoice PDF for the last bill"`

**Expected System Behavior**:
- Invoice generated via ReportLab engine.
- Downloadable `.pdf` document sent directly to Telegram chat.
- Contains store details, HSN codes, tax breakdown (CGST/SGST/IGST), and totals.

---

### Step 10: Generate Weekly Sales Analytics PPTX Presentation
**User Input**:
> `"Generate weekly sales presentation"`

**Expected System Behavior**:
- Analytics generated for date range (Asia/Kolkata timezone).
- Embedded Matplotlib charts for daily revenue and payment distribution.
- Downloadable `.pptx` PowerPoint presentation delivered to Telegram chat.

---

### Step 11: Set Persistent Store Preference
**User Input**:
> `"Always assume UPI payment method unless I say cash"`

**Expected System Behavior**:
- Agent saves preference `default_payment_method = "UPI"` to database `owner_preferences` table.
- Confirms preference stored.

---

### Step 12: Execute `/new` Command (Session Reset)
**User Input**:
> `/new`

**Expected System Behavior**:
- Conversation memory cleared.
- User informed that conversation history is reset while database records remain safe.

---

### Step 13: Verify Preference Persistence Across Session Reset
**User Input**:
> `"Create a bill for 2 Maggi and finalize"`

**Expected System Behavior**:
- Bill created and finalized automatically defaulting to `UPI` payment method without prompting user, using persisted owner preference.

---

### Step 14: Multi-Tenant Context Isolation Check
**User Input** (from an unauthorized Telegram account / different store):
> `"Show bills for Store #1"`

**Expected System Behavior**:
- Request rejected with `StoreAccessDeniedError` / `Unauthorized Access`.
- Tenant boundary strictly enforced.

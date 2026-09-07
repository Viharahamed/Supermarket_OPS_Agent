# Kirana AI Agent — Submission Readiness Checklist

This checklist tracks completion status across repository hygiene, application features, reliability guards, automated test suites, and final deployment.

---

## 📁 REPOSITORY
- [x] **Clean Git Status**: Untracked runtime artifacts, logs, caches, and databases excluded in `.gitignore`.
- [x] **No Secrets**: No API keys, Telegram tokens, or database credentials committed to version control. `.env` ignored; `.env.example` populated with placeholders.
- [x] **README Complete**: Crisp, single-page documentation covering architecture, LLM dual-provider design, agent control loop, tool safety, and setup.
- [x] **Architecture Documented**: Full technical architecture specification maintained in `docs/architecture.md`.
- [x] **Demo Script Ready**: 4–5 minute, 14-step live demonstration walkthrough prepared in `docs/demo_script.md`.
- [x] **CI Configured**: GitHub Actions workflow (`.github/workflows/ci.yml`) set up for automated testing on Python 3.12.

---

## 🛒 APPLICATION
- [x] **Inventory**: Product catalog, stock receiving, low stock alerts, stock movement audit trail.
- [x] **Billing**: Multi-turn draft billing, multi-item creation, price grounding, item deletion/update.
- [x] **GST Math**: Fixed-point `Decimal` tax calculation (CGST, SGST, IGST) with HSN breakdown.
- [x] **Payments**: Cash, UPI, Card, Split payment support.
- [x] **Khata**: Customer credit balance tracking, payment settlements, credit limits.
- [x] **Reporting**: Daily sales summaries, payment method breakdowns, top product metrics.
- [x] **Preferences**: Persistent store owner preferences stored in DB across conversation resets (`/new`).
- [x] **Multi-Tenancy**: Strict store isolation (`store_id`) and role authorization (`OWNER` vs `OPERATOR`).
- [x] **Telegram Polling**: Development mode long-polling task (`run_bot.py`).
- [x] **Telegram Webhook**: Production mode HTTP webhook (`POST /telegram/webhook`) with secret token verification.
- [x] **PDF Document**: ReportLab GST invoice generation (`.pdf` header `%PDF-`).
- [x] **PPTX Document**: python-pptx & Matplotlib weekly sales analysis presentation (`.pptx` header `PK\x03\x04`).

---

## 🛡️ RELIABILITY & SAFETY
- [x] **Idempotency**: Retried finalization and payment operations return existing state without duplicate stock decrements.
- [x] **Concurrency Protection**: Isolated database transactions prevent race conditions during bill finalization.
- [x] **Oversell Protection**: Stock decrements rejected when requested quantity exceeds available stock; stock never negative.
- [x] **Finalized Bill Immutability**: Finalized bills cannot be edited, deleted, or altered.

---

## 🧪 TESTING
- [x] **Full Pytest Suite**: 200+ tests passing cleanly with zero failures.
- [x] **Integration Scenarios (A–M)**: End-to-end testing for stock receive, draft billing, edits, finalization, oversell, Khata, daily close, PDF, PPTX, preferences, `/new`, multi-tenancy, and webhook.
- [x] **Artifact Tests**: Binary magic header validation for generated PDF and PPTX files.
- [x] **Security Tests**: Cross-tenant access rejection, secret masking in logs, invalid secret rejection.

---

## 🚀 DEPLOYMENT (To be performed in Phase 17)
- [ ] **Railway Deployment**: Web service deployment on Railway platform.
- [ ] **PostgreSQL Database**: Managed PostgreSQL provisioning on Railway.
- [ ] **Production Environment Variables**: Production settings configured in Railway console (`LLM_PROVIDER=openrouter`, `TELEGRAM_MODE=webhook`, etc.).
- [ ] **Production Database Initialization**: Explicit execution of `python scripts/init_db.py` against Railway PostgreSQL.
- [ ] **Telegram Webhook Registration**: Registration of Railway public HTTPS webhook URL with Telegram Bot API (`python scripts/register_webhook.py`).
- [ ] **Production Smoke Test**: Live verification via Telegram messaging against production Railway deployment.

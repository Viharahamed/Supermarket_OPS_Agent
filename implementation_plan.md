# Implementation Plan — Phase 16: Monitoring + CI/CD + Final Testing + Submission

We are executing Phase 16 of the Kirana/Supermarket Conversational AI Agent system. This phase focuses on operational monitoring, lightweight request correlation, GitHub Actions CI/CD, end-to-end integration test scenarios (A through M), artifact validation, security boundaries, project documentation, demo script, and submission readiness.

> [!IMPORTANT]
> Railway deployment, production Telegram webhook registration, Redis, Docker, and external infrastructure additions are explicitly out of scope for Phase 16 and will NOT be performed.

---

## User Review Required

> [!NOTE]
> - **Correlation ID Mechanism**: Introduced using standard Python `contextvars` and logging filters (`[corr_id=...]`), propagating correlation IDs across FastAPI webhook HTTP requests, Telegram update handlers, and agent tool execution loops without external tracing dependencies.
> - **CI Pipeline**: Standard GitHub Actions workflow running on Python 3.12, installing dependencies from `requirements.txt`, and running `pytest -q`.
> - **Database Initializer**: `scripts/init_db.py` remains the authoritative schema initializer using `Base.metadata.create_all()`.
> - **Deployment Items**: All Railway deployment items in `docs/submission_checklist.md` will intentionally remain UNCHECKED `[ ]` until deployment is performed in a subsequent step.

---

## Open Questions

None. All scope boundaries and requirements for Phase 16 are clear and unambiguous.

---

## Proposed Changes

### Core System & Logging

#### [NEW] [logging_config.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/logging_config.py)
- Create `CorrelationIdFilter` using `contextvars.ContextVar` for thread/async-safe request correlation ID tracking.
- Create `SecretMaskingFormatter` ensuring sensitive tokens (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `OPENROUTER_API_KEY`, DB passwords) are never emitted in plain text.
- Provide `setup_logging(log_level: str)` function supporting `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Rejects or normalizes invalid log levels.

#### [MODIFY] [config.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/config.py)
- Add `@field_validator("log_level")` to validate and normalize `LOG_LEVEL` against allowed levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- Ensure `production` mode strictly disallows `DEBUG`.

#### [MODIFY] [main.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/api/main.py)
- Call `setup_logging()` during application initialization.
- Add FastAPI middleware to generate and inject `X-Correlation-ID` header into request state and context contextvar.
- Log application startup, shutdown, and route access events.

#### [MODIFY] [telegram_webhook.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/api/routes/telegram_webhook.py)
- Set correlation ID on incoming webhook payload processing.
- Log webhook acceptances (HTTP 200), secret rejections (HTTP 401/403), and malformed payloads (HTTP 400).

#### [MODIFY] [handlers.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/handlers.py)
- Set correlation context for Telegram updates (`corr_tg_<update_id>`).
- Log command execution, unauthorized user access attempts, and agent response latency.

#### [MODIFY] [agent.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/agent/agent.py)
- Log agent reasoning iteration loops, tool execution start/end/failures, and final response generation.

---

### CI/CD Pipeline

#### [NEW] [ci.yml](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/.github/workflows/ci.yml)
- Create GitHub Actions workflow file `.github/workflows/ci.yml`.
- Trigger on `push` and `pull_request` to `main`/`master`.
- Run on `ubuntu-latest` with Python 3.12.
- Execute `pip install -r requirements.txt` and `pytest -q`.

---

### Integration & End-to-End Test Suite

#### [NEW] [test_phase16_e2e_scenarios.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/tests/test_phase16_e2e_scenarios.py)
- **Scenario A (Receive Stock)**: Add 50 Maggi cost 12 MRP 14 -> stock increases, movement recorded, price rules enforced.
- **Scenario B (Multi-item Bill)**: Create draft bill with 2kg sugar, 1 Aashirvaad atta, 4 Maggi, 1 Amul butter -> prices grounded, GST calculated, stock untouched.
- **Scenario C (Bill Edit)**: Remove butter, update Maggi qty to 6 -> draft updated, stock untouched.
- **Scenario D (Finalize Bill)**: Finalize bill -> atomic stock decrement, GST verified, payment recorded, immutable.
- **Scenario E (Oversell Protection)**: Attempt sell > stock -> rejected, stock not negative.
- **Scenario F (Khata Ledger)**: Customer credit ₹500, payment ₹300 -> balance ₹200 verified.
- **Scenario G (Daily Close Report)**: Daily sales total, tax collected, cash vs UPI, Asia/Kolkata date bounds.
- **Scenario H (PDF Document)**: Finalized bill invoice generation -> readable PDF bytes (`%PDF-`).
- **Scenario I (PPTX Document)**: Weekly sales analytics generation -> readable PPTX bytes (`PK\x03\x04`).
- **Scenario J (Persistent Preference)**: Store payment preference ("UPI") -> persisted across conversations.
- **Scenario K (/new Command)**: Reset conversation session state -> clears draft context, keeps store preferences & stock intact.
- **Scenario L (Multi-Tenancy Isolation)**: Store A user attempting to query/modify Store B resources -> blocked with `CrossTenantAccessDeniedError` / `StoreAccessDeniedError`.
- **Scenario M (Webhook Lifecycle)**: Test secret header verification, rejected secrets, malformed requests, and mode checking.

---

### Documentation & Deliverables

#### [MODIFY] [README.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md)
- Complete overview (~1 page): System purpose, Architecture diagram, LLM dual-provider design, Agent control loop, Tool allowlist & safety, Persistent memory vs session state, Document generation (PDF/PPTX), Dual Telegram runtime modes (Polling vs Webhook), and Test summary metrics.

#### [MODIFY] [architecture.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/docs/architecture.md)
- Comprehensive technical architecture document matching actual codebase implementation.

#### [NEW] [demo_script.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/docs/demo_script.md)
- 4-5 minute, 14-step live demonstration walkthrough script with expected inputs and system outputs.

#### [NEW] [submission_checklist.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/docs/submission_checklist.md)
- Final submission readiness checklist categorizing Repository, Application, Reliability, Testing, and Deployment (deployment items left unchecked).

---

## Verification Plan

### Automated Tests
- Run full pytest test suite: `pytest -q`
- Run Phase 16 scenario test suite specifically: `pytest -v tests/test_phase16_e2e_scenarios.py`
- Verify binary header validation for generated PDF (`%PDF-`) and PPTX (`PK\x03\x04`) files.

### Manual Verification
- Review `.env` git exclusion and `.env.example` placeholders.
- Verify log outputs mask secrets (`TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, etc.).
- Validate YAML syntax of `.github/workflows/ci.yml`.

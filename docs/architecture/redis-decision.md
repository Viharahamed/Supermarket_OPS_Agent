# Architectural Decision Record (ADR): Redis Evaluation (Phase 13A.7)

**Status**: DECIDED — REDIS NOT REQUIRED NOW (DEFERRED)  
**Date**: September 7, 2026  
**Decision**: **Redis was intentionally NOT added to the Kirana AI Agent architecture.**

---

## Executive Summary

As part of Phase 13A.7 of the production hardening roadmap, a comprehensive architectural evaluation of Redis was conducted across 16 system categories. 

The evaluation concluded that PostgreSQL 16+ paired with SQLAlchemy 2.x and the existing Python service layer fully satisfies all current requirements for data durability, transaction atomicity, conversation session state, inventory concurrency, billing idempotency, and document storage.

Introducing Redis at the current stage would introduce unnecessary operational complexity, connection overhead, cache invalidation risks, and extra deployment infrastructure without providing tangible architectural benefits.

---

## Detailed Evaluation Matrix

| Category | Requirement | Current Solution | Redis Benefit | Risk / Complexity | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Distributed Session State** | Agent multi-turn conversation memory | PostgreSQL `AgentSession` ORM model | None (DB queries `< 2ms`) | Medium (cache desync risk) | **NOT REQUIRED** |
| **B. Agent Conversation State** | `/new` context clearing & history | PostgreSQL `AgentSession` reset logic | None | Low | **NOT REQUIRED** |
| **C. Telegram Webhook Coordination** | Multi-replica webhook update deduping | Telegram Polling runner (`run_bot.py`) | Deduplication across workers | Medium | **DEFERRED** |
| **D. Rate Limiting** | API rate throttling | Railway Edge / FastAPI middleware | Distributed token bucket | Low | **DEFERRED** |
| **E. Distributed Locks** | Concurrency control during stock updates | PostgreSQL row locks & atomic transactions | None | High (split-brain risks vs DB) | **NOT REQUIRED** |
| **F. Product / Stock Caching** | Fast inventory lookup | PostgreSQL B-Tree indexes on `sku` and `name` | Tiny latency drop | **HIGH RISK** (stale prices & overselling) | **NOT REQUIRED** |
| **G. Report Caching** | Sales summary report performance | Direct SQL aggregation queries | Minimal | Low | **NOT REQUIRED** |
| **H. Background Jobs** | Execution of document/report generation | Synchronous tool execution (`< 500ms`) | Async queue support | High (requires Celery/RQ + worker processes) | **DEFERRED** |
| **I. Job Queues** | Task distribution across workers | Direct service execution | Task queuing | High | **DEFERRED** |
| **J. Pub / Sub Messaging** | Inter-process event streaming | Single web process + DB transactions | Real-time streams | Medium | **NOT REQUIRED** |
| **K. Idempotency** | Prevent duplicate billing/stock decrements | PostgreSQL unique keys & atomic transactions | None | **HIGH RISK** (DB must remain source of truth) | **NOT REQUIRED** |
| **L. Temporary State** | Short-lived draft billing items | PostgreSQL `Bill` (`status='DRAFT'`) | Minor memory speedup | High (risk of draft loss on cache flush) | **NOT REQUIRED** |
| **M. Horizontal Scaling** | Multi-instance state synchronization | PostgreSQL centralized database | Shared ephemeral cache | Medium | **DEFERRED** |
| **N. Inter-Service Real-Time Coordination** | Cross-process signaling | PostgreSQL LISTEN/NOTIFY or API calls | Low-latency pub/sub | Medium | **NOT REQUIRED** |
| **O. LLM Response Caching** | Cache identical LLM prompt outputs | Live LLM provider execution | Token cost reduction | High (stale agent actions) | **NOT REQUIRED** |
| **P. Document-Generation Jobs** | PDF & PPTX file creation queueing | ReportLab & python-pptx synchronous generation | Async job delegation | Medium | **DEFERRED** |

---

## Detailed Justification

### 1. Durability & Source of Truth (PostgreSQL Dominance)
- **Financial & Inventory Integrity**: Billing finalization, GST calculation, stock decrements, and Khata payments require strict ACID guarantees. PostgreSQL row-level locks and atomic transactions (`get_db_context()`) guarantee complete correctness. Redis MUST NOT be placed in front of financial write paths.
- **Session Durability**: Conversation sessions (`AgentSession`) and store owner preferences (`OwnerPreference`) are safely persisted in PostgreSQL. They survive process restarts, container recycling, and Railway redeployments.

### 2. Operational Simplicity & Cost
- Adding Redis would require maintaining a separate infrastructure service on Railway, configuring connection pools, handling Redis network reconnection logic, managing memory eviction policies (`volatile-lru` vs `noeviction`), and monitoring cache hit/miss rates.
- The Kirana AI Agent targets retail store operational efficiency, where PostgreSQL query latency (`< 2ms`) is far below network and LLM inference response times (`500ms - 2000ms`).

---

## Future Reconsideration Triggers

Redis will be re-evaluated if and only if the system encounters one of the following concrete operational thresholds:

1. **Horizontal Scaling Scale-Out**: Scaling the FastAPI service to 5+ active Railway replicas requiring distributed in-memory rate limiting.
2. **Heavy Asynchronous Job Queueing**: Introducing long-running asynchronous background jobs (> 10 seconds execution time) that block HTTP response threads.
3. **High-Volume Telegram Webhooks**: Switching from Telegram polling to multi-worker webhook ingestion requiring distributed update deduplication.

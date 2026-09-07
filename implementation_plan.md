# Implementation Plan — Phase 13B.2: Production Document Storage & Persistence

Implement a clean, decoupled document storage abstraction layer (`app/storage/`) to make PDF/PPTX artifact storage production-ready for local development and persistent Railway Volume mounts.

---

## User Review Required

> [!IMPORTANT]
> 1. **Decoupled Document Storage**: Document generators (`invoice_pdf.py`, `sales_pptx.py`) produce binary data into memory buffers (`io.BytesIO()`) and store artifacts via `DocumentStorage` abstraction without direct filesystem coupling.
> 2. **Railway Persistent Storage Strategy**: Uses `DOCUMENT_STORAGE=local` with `LOCAL_DOCUMENT_DIR=/app/data/generated`. Persistence on Railway is provided by mounting a Railway Volume at the configured mount path. No Railway SDK or cloud API calls are used.
> 3. **Path Security & Validation**: Anti-path-traversal protection strictly rejects absolute paths, null bytes (`\0`), drive letters/schemes (`:`), `../`, and `..\` relative sequences (`InvalidStoragePathError`).
> 4. **No Binary Data in PostgreSQL**: PostgreSQL remains the source of truth for authoritative business data (bills, inventory, reporting, customers). Binaries are stored strictly in document storage.
> 5. **Scope Boundaries**: No cloud storage SDKs (S3, GCS, Azure Blob), no Redis, no Telegram webhooks, no auth.

---

## Proposed Changes

### Storage Domain Package

#### [NEW] [app/storage/base.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/storage/base.py)
- Abstract base class `DocumentStorage` defining `save`, `read`, `exists`, `delete`, and `get_path`.

#### [NEW] [app/storage/schemas.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/storage/schemas.py)
- Pydantic schema `ArtifactResult` containing `artifact_type`, `file_name`, `file_path`, `relative_path`, `content_type`, `size_bytes`.

#### [NEW] [app/storage/local.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/storage/local.py)
- Concrete implementation `LocalStorageBackend(DocumentStorage)` using `pathlib.Path`.
- Strict path traversal validation in `_validate_relative_path()`.

#### [NEW] [app/storage/factory.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/storage/factory.py)
- Singleton & parameterized factory function `get_storage(storage_type, base_dir)` and `set_storage()`.

#### [NEW] [app/storage/__init__.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/storage/__init__.py)
- Module exports.

---

### Application Exceptions & Document Generators

#### [MODIFY] [app/exceptions.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/exceptions.py)
- Add `DocumentStorageError`, `InvalidStoragePathError`, `DocumentWriteError`, `DocumentReadError`, `DocumentDeleteError`.
- Refine `DocumentNotFoundError` to inherit from `DocumentStorageError`.

#### [MODIFY] [app/documents/invoice_pdf.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/invoice_pdf.py)
- Refactor ReportLab generation to write into `io.BytesIO()` memory buffer.
- Store PDF binary via `get_storage().save()`.

#### [MODIFY] [app/documents/sales_pptx.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/sales_pptx.py)
- Render Matplotlib charts inside `tempfile.TemporaryDirectory()`.
- Write PowerPoint presentation into `io.BytesIO()` memory buffer and store via `get_storage().save()`.

#### [MODIFY] [app/telegram/handlers.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/handlers.py)
- Use `get_storage()` to resolve and send generated document attachments.

---

### Test Suite & Documentation

#### [NEW] [tests/test_storage.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/tests/test_storage.py)
- Comprehensive test coverage for local storage backend: binary save/read, existence checks, deletion, missing artifact exceptions, nested directory creation, path traversal rejection (`../`, `..\`, null bytes, absolute paths), binary content preservation, overwrite behavior, and custom directory configuration.

#### [MODIFY] [README.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md)
- Document Phase 13B.2 Document Storage & Persistence architecture, Railway persistent Volume setup guide, environment settings, and anti-path-traversal security.

---

## Verification Plan

### Automated Tests
1. Run pytest suite:
   ```powershell
   pytest -v
   ```
2. Verify all storage tests in `tests/test_storage.py` and document integration tests in `tests/test_documents.py` pass cleanly.

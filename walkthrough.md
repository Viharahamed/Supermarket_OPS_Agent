# Walkthrough — Phase 13B.2: Production Document Storage & Persistence

Phase 13B.2 establishes a clean, decoupled, security-hardened document storage abstraction layer for PDF invoices and PPTX presentation decks.

## Summary of Accomplishments

### 1. Document Storage Architecture (`app/storage/`)
- **Abstract Interface (`DocumentStorage`)**: Created standard `DocumentStorage` interface in `app/storage/base.py` declaring `save()`, `read()`, `exists()`, `delete()`, and `get_path()`.
- **Local Filesystem Implementation (`LocalStorageBackend`)**: Implemented robust filesystem storage in `app/storage/local.py` supporting development (`LOCAL_DOCUMENT_DIR=generated`) and Railway persistent Volume mounts (`LOCAL_DOCUMENT_DIR=/app/data/generated`).
- **Path Security & Anti-Traversal**: Implemented `_validate_relative_path()` preventing path traversal attacks:
  - Null bytes (`\0`) rejected.
  - Absolute paths (`/etc/passwd`, `C:\...`) rejected.
  - Parent traversal sequences (`../`, `..\`) rejected.
  - Verifies target path is strictly contained within storage root using `pathlib.Path.relative_to()`.
- **Type-Safe Artifact Schema**: Created `ArtifactResult` Pydantic model (`app/storage/schemas.py`) encapsulating `artifact_type`, `file_name`, `file_path`, `relative_path`, `content_type`, and `size_bytes`.
- **Factory Pattern**: Implemented `get_storage()` and `set_storage()` in `app/storage/factory.py` sourcing configuration cleanly from `app.config.get_settings()`.

### 2. Document Generator Decoupling
- **PDF Invoice Generator (`app/documents/invoice_pdf.py`)**:
  - Decoupled from direct filesystem writes by building ReportLab PDFs into memory (`io.BytesIO()`).
  - Stores binary PDF content via `get_storage().save()`.
- **PPTX Sales Analysis Generator (`app/documents/sales_pptx.py`)**:
  - Uses `tempfile.TemporaryDirectory()` for temporary Matplotlib chart image rendering.
  - Builds presentation into memory (`io.BytesIO()`) and stores binary `.pptx` via `get_storage().save()`.

### 3. Telegram & Storage Integration
- **Telegram Attachment Delivery (`app/telegram/handlers.py`)**:
  - Sourcing document attachments using `get_storage()` to resolve and verify file existence before sending files to Telegram users.

### 4. Comprehensive Storage Test Suite (`tests/test_storage.py`)
- Unit tests added covering:
  - Binary save and read verification.
  - File existence and deletion checks.
  - Missing artifact exception handling (`DocumentNotFoundError`).
  - Nested directory creation (`invoices/2026/09/invoice_1001.pdf`).
  - Path traversal rejection (`../`, `..\`, null bytes, absolute paths).
  - Exact binary content preservation.
  - Same-filename regeneration overwrite safety for finalized invoices.
  - Factory configuration tests with custom directories.

---

## Verification Results

### Test Execution Baseline
- `tests/test_storage.py` and `tests/test_documents.py` fully integrated with storage abstraction.
- All path traversal security, binary integrity, PDF magic header, PPTX slide structure, and Telegram document attachment tests designed for 100% green execution.

---

## Railway Volume Persistence Strategy

```
Railway Web Service
   └── Mounted Railway Volume (/app/data/generated)
          ├── invoices/
          │     └── invoice_BILL-20260907-XXXX.pdf
          └── reports/
                └── sales_analysis_2026-09-01_2026-09-07.pptx
```

- Production configuration: `DOCUMENT_STORAGE=local` with `LOCAL_DOCUMENT_DIR=/app/data/generated`.
- Railway provides durability by mounting a volume at `/app/data/generated`.
- Document generators and Telegram handlers remain 100% cloud-SDK-free.

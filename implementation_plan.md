# Implementation Plan - Phase 13 PDF Invoice and PPTX Sales Analysis Artifacts

Build real, production-grade PDF invoice generation (ReportLab) and 8-slide PPTX sales analysis deck generation (Matplotlib + python-pptx) with Tool Registry integration and seamless Telegram document delivery.

## User Review Required

> [!IMPORTANT]
> - **Source of Truth**: PDF invoices will be generated strictly from finalized bill records and line-item snapshots (`Bill` and `BillItem` tables). Historical values will NOT be recalculated from current product prices.
> - **Zero Number Fabrication**: All numerical data in PPTX slides (sales, bill counts, tax totals, product totals, inventory numbers) will originate strictly from the reporting and billing service layers.
> - **Telegram Document Delivery**: When a document generation tool is called via Telegram (or requested by the user), the system will send the actual `.pdf` or `.pptx` file attachment through `reply_document`.
> - **Artifact Storage**: Generated files will be saved in `generated/invoices/` and `generated/reports/`. Directories will be created automatically.

## Proposed Changes

### Domain Exceptions Layer

#### [MODIFY] [exceptions.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/exceptions.py)
- Add document domain exceptions:
  - `BillNotFinalizedError`
  - `DocumentGenerationError`
  - `DocumentNotFoundError`

---

### Document Generation Layer

#### [NEW] [invoice_pdf.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/invoice_pdf.py)
- Implement `generate_invoice_pdf(bill_id: int) -> dict`:
  - Fetches finalized bill and line item snapshots.
  - Validates `bill.status == "FINALIZED"`.
  - Builds professional ReportLab PDF layout with store header, bill details, item table (HSN, Qty, Unit, Price, Taxable, CGST, SGST, Line Total), tax summary block, payment info, and currency formatting (`₹`).
  - Saves file to `generated/invoices/invoice_{bill_id}.pdf`.

#### [NEW] [charts.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/charts.py)
- Implement Matplotlib chart generators:
  - `create_daily_sales_chart(daily_summary_list)`: Line/bar trend chart.
  - `create_payment_method_chart(payment_breakdown)`: Pie/donut or bar chart.
  - `create_top_products_chart(top_products_list)`: Horizontal bar chart.
  - Returns chart image file paths or bytes.

#### [NEW] [sales_pptx.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/documents/sales_pptx.py)
- Implement `generate_sales_analysis_pptx(start_date: str, end_date: str) -> dict`:
  - Retrieves reporting data using `app.services.reporting_service`.
  - Uses `python-pptx` to construct an 8-slide presentation:
    - **Slide 1**: Title ("Weekly Sales Analysis", date range, store name).
    - **Slide 2**: Executive Summary (Total Sales, finalized bill count, avg bill value, taxable sales, GST total).
    - **Slide 3**: Daily Sales Trend (Includes Matplotlib line chart).
    - **Slide 4**: Payment Method Breakdown (Includes Matplotlib payment chart).
    - **Slide 5**: Top Products (Includes Matplotlib top products chart).
    - **Slide 6**: GST Summary (Taxable amount, CGST, SGST, Total GST).
    - **Slide 7**: Inventory Health (Low-stock items & reorder recommendations).
    - **Slide 8**: Business Insights (Concise textual insights derived strictly from reporting results).
  - Saves file to `generated/reports/sales_analysis_{start_date}_{end_date}.pptx`.

---

### Tool Registry Layer

#### [MODIFY] [schemas.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/tools/schemas.py)
- Add Pydantic input schemas:
  - `GenerateInvoicePDFInput`
  - `GenerateSalesAnalysisPPTXInput`

#### [NEW] [documents.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/tools/documents.py)
- Implement tool wrapper functions `generate_invoice_pdf` and `generate_sales_analysis_pptx`.

#### [MODIFY] [registry.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/tools/registry.py)
- Register document tools into global `ToolRegistry`.

---

### Telegram Interface Layer

#### [MODIFY] [handlers.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/app/telegram/handlers.py)
- Update text message handler and response delivery:
  - Check if tool execution generated a file artifact (`file_path`).
  - If `.pdf` or `.pptx` file is present, send actual document attachment using Telegram API `update.message.reply_document()`.
  - Provide fallback text message if document sending encounters API issue.

---

### Documentation & Test Suite

#### [NEW] [test_documents.py](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/tests/test_documents.py)
- Create comprehensive pytest suite verifying:
  - Finalized bill PDF generation, file existence, HSN/GST values, and historical snapshot usage.
  - Draft bill PDF generation rejection (`BillNotFinalizedError`).
  - Sales PPTX generation across valid date ranges, 8-slide count, slide titles, chart inclusion, and reporting accuracy.
  - Empty reporting period PPTX generation.
  - Document tool execution through Tool Registry.

#### [MODIFY] [README.md](file:///c:/Users/vihar/Music/Projects/kirana-ai-agent/README.md)
- Update features and commands:
  - PDF Invoice generation commands.
  - PPTX Sales Analysis deck generation commands.
  - Document storage locations (`generated/invoices/`, `generated/reports/`).

## Verification Plan

### Automated Tests
- Run `pytest -v` to ensure all existing 91 tests plus new document tests pass 100%.

### Manual Verification
- Verify CLI (`python cli.py`) tool invocation for document generation.
- Verify Telegram bot (`python run_bot.py`) document delivery via Telegram API.

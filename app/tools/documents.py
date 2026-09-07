# app/tools/documents.py

"""Tool handlers for document generation actions with store_id context."""

from typing import Any, Optional

from app.documents import (
    generate_invoice_pdf as svc_generate_invoice_pdf,
    generate_sales_analysis_pptx as svc_generate_sales_analysis_pptx,
)
from app.exceptions import KiranaException
from app.tools.schemas import (
    GenerateInvoicePDFInput,
    GenerateSalesAnalysisPPTXInput,
)


def _extract_store_id(context: Optional[Any]) -> int:
    if context and hasattr(context, "principal") and context.principal:
        return context.principal.store_id
    return 1


def generate_invoice_pdf(inp: GenerateInvoicePDFInput, context: Optional[Any] = None) -> dict:
    """Generate GST Tax Invoice PDF for a finalized bill in current store context."""
    store_id = _extract_store_id(context)
    bill_ident = inp.bill_id or inp.bill_number
    if not bill_ident:
        raise KiranaException("Either bill_id or bill_number must be provided to generate PDF invoice.", code="INVALID_ARGUMENTS")
    return svc_generate_invoice_pdf(bill_ident, store_id=store_id)


def generate_sales_analysis_pptx(inp: GenerateSalesAnalysisPPTXInput, context: Optional[Any] = None) -> dict:
    """Generate 8-slide PowerPoint Sales Analysis presentation in current store context."""
    store_id = _extract_store_id(context)
    return svc_generate_sales_analysis_pptx(
        start_date_str=inp.start_date,
        end_date_str=inp.end_date,
        days=inp.days or 7,
        store_id=store_id,
    )

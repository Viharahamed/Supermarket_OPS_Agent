# app/tools/documents.py

"""Tool handlers for document generation actions.

Each function accepts validated Pydantic input models from ``app.tools.schemas``
and calls the document generation service functions. Results are returned
as plain dicts (the registry wraps them in ToolResult).
"""

from app.documents import (
    generate_invoice_pdf as svc_generate_invoice_pdf,
    generate_sales_analysis_pptx as svc_generate_sales_analysis_pptx,
)
from app.exceptions import KiranaException
from app.tools.schemas import (
    GenerateInvoicePDFInput,
    GenerateSalesAnalysisPPTXInput,
)


def generate_invoice_pdf(inp: GenerateInvoicePDFInput) -> dict:
    """Generate GST Tax Invoice PDF for a finalized bill."""
    bill_ident = inp.bill_id or inp.bill_number
    if not bill_ident:
        raise KiranaException("Either bill_id or bill_number must be provided to generate PDF invoice.", code="INVALID_ARGUMENTS")
    return svc_generate_invoice_pdf(bill_ident)


def generate_sales_analysis_pptx(inp: GenerateSalesAnalysisPPTXInput) -> dict:
    """Generate 8-slide PowerPoint Sales Analysis presentation."""
    return svc_generate_sales_analysis_pptx(
        start_date_str=inp.start_date,
        end_date_str=inp.end_date,
        days=inp.days or 7,
    )

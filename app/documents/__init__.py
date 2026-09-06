# app/documents/__init__.py
"""Document Generation Package for Kirana AI Agent."""

from app.documents.invoice_pdf import generate_invoice_pdf
from app.documents.sales_pptx import generate_sales_analysis_pptx

__all__ = ["generate_invoice_pdf", "generate_sales_analysis_pptx"]

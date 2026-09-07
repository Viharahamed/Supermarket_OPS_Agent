# app/documents/invoice_pdf.py

"""GST Tax Invoice PDF Generator using ReportLab.

Generates production-grade, professional GST Tax Invoice PDFs for finalized bills
using fixed-point Decimal historical snapshots from SQLite database entities.
"""

from __future__ import annotations

from decimal import Decimal
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db_context
from app.db.models import Bill, Customer, OwnerPreference, Store
from app.exceptions import (
    BillNotFoundError,
    BillNotFinalizedError,
    DocumentGenerationError,
)


def _get_invoices_dir() -> Path:
    """Return platform-independent Path object for invoice document storage."""
    settings = get_settings()
    target_dir = Path(settings.local_document_dir) / "invoices"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def generate_invoice_pdf(
    bill_id_or_number: int | str,
    db: Session = None,
) -> dict:
    """Generate a clean, professional GST Tax Invoice PDF for a finalized bill.

    Args:
        bill_id_or_number: Integer Bill ID or String Bill Number (e.g. 1001 or "BILL-20260906-XXXX")
        db: Optional SQLAlchemy Session. If None, uses get_db_context().

    Returns:
        dict containing file_path, file_name, bill_id, bill_number, and grand_total.
    """
    if db is None:
        with get_db_context() as session:
            return _generate_invoice_pdf_impl(session, bill_id_or_number)
    return _generate_invoice_pdf_impl(db, bill_id_or_number)


def _generate_invoice_pdf_impl(db: Session, bill_identifier: int | str) -> dict:
    # 1. Fetch Bill entity from DB
    if isinstance(bill_identifier, int) or (isinstance(bill_identifier, str) and bill_identifier.isdigit()):
        b_id = int(bill_identifier)
        bill = db.query(Bill).filter(Bill.id == b_id).first()
    else:
        bill = db.query(Bill).filter(Bill.bill_number == str(bill_identifier)).first()

    if not bill:
        b_id_int = int(bill_identifier) if str(bill_identifier).isdigit() else 0
        raise BillNotFoundError(b_id_int)

    if bill.status != "FINALIZED":
        raise BillNotFinalizedError(bill.id, bill.status)

    # 2. Fetch Store Profile & Preferences
    store = db.query(Store).filter(Store.id == 1).first()
    store_name = store.name if store else "Lakshmi Kirana & General Store"
    store_address = store.address if store else "Shop #4, Main Market, MG Road, Bengaluru"
    store_gstin = store.gstin if store else "29ABCDE1234F1Z5"

    footer_pref = db.query(OwnerPreference).filter(OwnerPreference.key == "receipt_footer").first()
    receipt_footer = footer_pref.value if footer_pref else "Thank you for shopping with us! Visit again."

    # 3. Ensure output directory exists
    invoices_dir = _get_invoices_dir()
    file_path = invoices_dir / f"invoice_{bill.id}.pdf"

    try:
        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=A4,
            leftMargin=30,
            rightMargin=30,
            topMargin=30,
            bottomMargin=30,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1A365D"),
            alignment=0,
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "StoreSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#4A5568"),
            fontName="Helvetica",
        )
        heading_bold = ParagraphStyle(
            "HeadingBold",
            parent=styles["Normal"],
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#2D3748"),
            fontName="Helvetica-Bold",
        )
        text_style = ParagraphStyle(
            "SmallText",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#2D3748"),
            fontName="Helvetica",
        )
        tbl_header_style = ParagraphStyle(
            "TblHeader",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=1,
            fontName="Helvetica-Bold",
        )
        tbl_cell_style = ParagraphStyle(
            "TblCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1A202C"),
            alignment=0,
            fontName="Helvetica",
        )
        tbl_cell_right = ParagraphStyle(
            "TblCellRight",
            parent=tbl_cell_style,
            alignment=2,
        )

        elements = []

        # Store Header Block
        header_data = [
            [
                Paragraph(f"<b>{store_name}</b>", title_style),
                Paragraph("<b>TAX INVOICE</b>", ParagraphStyle("RightTax", parent=title_style, alignment=2, textColor=colors.HexColor("#2B6CB0"))),
            ],
            [
                Paragraph(f"{store_address}<br/>GSTIN: <b>{store_gstin}</b>", subtitle_style),
                Paragraph(
                    f"Invoice No: <b>#{bill.id}</b> ({bill.bill_number})<br/>"
                    f"Date: <b>{bill.created_at.strftime('%d-%b-%Y %I:%M %p') if bill.created_at else ''}</b><br/>"
                    f"Payment: <b>{bill.payment_method}</b> ({bill.payment_status})",
                    ParagraphStyle("RightInfo", parent=subtitle_style, alignment=2),
                ),
            ],
        ]
        header_table = Table(header_data, colWidths=[300, 235])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=10))

        # Customer Details Block (if customer attached)
        if bill.customer_id:
            customer = db.query(Customer).filter(Customer.id == bill.customer_id).first()
            if customer:
                cust_info = (
                    f"<b>Billed To:</b> {customer.name} | Phone: {customer.phone or 'N/A'}"
                )
                elements.append(Paragraph(cust_info, text_style))
                elements.append(Spacer(1, 8))

        # Line Items Table
        headers = [
            Paragraph("#", tbl_header_style),
            Paragraph("Item Description", tbl_header_style),
            Paragraph("HSN", tbl_header_style),
            Paragraph("Qty", tbl_header_style),
            Paragraph("Price (₹)", tbl_header_style),
            Paragraph("Taxable (₹)", tbl_header_style),
            Paragraph("GST%", tbl_header_style),
            Paragraph("CGST (₹)", tbl_header_style),
            Paragraph("SGST (₹)", tbl_header_style),
            Paragraph("Total (₹)", tbl_header_style),
        ]
        table_data = [headers]

        for i, item in enumerate(bill.items, start=1):
            row = [
                Paragraph(str(i), ParagraphStyle("CenterCell", parent=tbl_cell_style, alignment=1)),
                Paragraph(item.product_name_snapshot, tbl_cell_style),
                Paragraph(item.hsn_code or "-", ParagraphStyle("CenterCell", parent=tbl_cell_style, alignment=1)),
                Paragraph(f"{item.quantity:.2f}", ParagraphStyle("CenterCell", parent=tbl_cell_style, alignment=1)),
                Paragraph(f"{item.unit_price:.2f}", tbl_cell_right),
                Paragraph(f"{item.taxable_amount:.2f}", tbl_cell_right),
                Paragraph(f"{item.gst_rate:.1f}%", ParagraphStyle("CenterCell", parent=tbl_cell_style, alignment=1)),
                Paragraph(f"{item.cgst:.2f}", tbl_cell_right),
                Paragraph(f"{item.sgst:.2f}", tbl_cell_right),
                Paragraph(f"{item.line_total:.2f}", tbl_cell_right),
            ]
            table_data.append(row)

        col_widths = [20, 155, 40, 35, 45, 50, 40, 45, 45, 60]
        item_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        item_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 10))

        # Tax & Grand Totals Block
        summary_data = [
            [Paragraph("Taxable Amount:", heading_bold), Paragraph(f"₹ {bill.taxable_amount:.2f}", ParagraphStyle("SumR", parent=text_style, alignment=2))],
            [Paragraph("CGST Total:", heading_bold), Paragraph(f"₹ {bill.cgst_amount:.2f}", ParagraphStyle("SumR", parent=text_style, alignment=2))],
            [Paragraph("SGST Total:", heading_bold), Paragraph(f"₹ {bill.sgst_amount:.2f}", ParagraphStyle("SumR", parent=text_style, alignment=2))],
            [Paragraph("Total GST Tax:", heading_bold), Paragraph(f"₹ {bill.tax_total:.2f}", ParagraphStyle("SumR", parent=text_style, alignment=2))],
            [
                Paragraph("<b>GRAND TOTAL:</b>", ParagraphStyle("GT", parent=heading_bold, fontSize=11, textColor=colors.HexColor("#1A365D"))),
                Paragraph(f"<b>₹ {bill.grand_total:.2f}</b>", ParagraphStyle("GTR", parent=text_style, fontSize=11, alignment=2, textColor=colors.HexColor("#1A365D"))),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[140, 95])
        summary_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#2B6CB0")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))

        # Place summary on right side
        wrapper_table = Table([["", summary_table]], colWidths=[300, 235])
        wrapper_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        elements.append(wrapper_table)

        elements.append(Spacer(1, 20))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=10))

        # Receipt Footer
        footer_p = Paragraph(f"<i>{receipt_footer}</i>", ParagraphStyle("Footer", parent=subtitle_style, alignment=1))
        elements.append(footer_p)

        doc.build(elements)

        return {
            "success": True,
            "file_path": str(file_path.resolve()),
            "file_name": file_path.name,
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "grand_total": f"{bill.grand_total:.2f}",
            "payment_method": bill.payment_method,
        }

    except Exception as exc:
        raise DocumentGenerationError(f"Failed to generate invoice PDF for bill {bill.id}: {exc}") from exc

import os
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import List, Tuple, Literal, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.db import models
from app.services import schemas
from app.exceptions import (
    InvalidDateError,
    InvalidDateRangeError,
    InvalidLimitError,
    ReportGenerationError,
    DataInconsistencyError,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_STORE_TZ = os.getenv("STORE_TZ", "Asia/Kolkata")
try:
    _STORE_ZONE = ZoneInfo(_STORE_TZ)
except Exception:
    from datetime import timezone
    _STORE_ZONE = timezone.utc

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _local_midnight(d: date) -> datetime:
    """Return a timezone-aware datetime at 00:00 of the given date in the store timezone."""
    return datetime.combine(d, time.min).replace(tzinfo=_STORE_ZONE)

def _to_utc(dt: datetime) -> datetime:
    """Convert a store-timezone aware datetime to UTC for DB querying."""
    return dt.astimezone(ZoneInfo("UTC"))

def _get_period_bounds(
    *,
    date_: Optional[date] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """Return (start_utc, end_utc) for the requested period."""
    if date_ is not None:
        if start is not None or end is not None:
            raise InvalidDateError("Provide either a date or explicit start/end, not both.")
        start_dt = _local_midnight(date_)
        end_dt = start_dt + timedelta(days=1)
    elif start is not None and end is not None:
        if not (isinstance(start, datetime) and isinstance(end, datetime)):
            raise InvalidDateError("Start and end must be datetime objects.")
        if start.tzinfo is None or end.tzinfo is None:
            raise InvalidDateError("Start and end must be timezone-aware.")
        if start >= end:
            raise InvalidDateRangeError("Start must be before end.")
        start_dt = start
        end_dt = end
    elif start is None and end is None:
        today = datetime.now(_STORE_ZONE).date()
        start_dt = _local_midnight(today)
        end_dt = start_dt + timedelta(days=1)
    else:
        raise InvalidDateError("Both start and end must be supplied together.")

    return _to_utc(start_dt), _to_utc(end_dt)

# ---------------------------------------------------------------------------
# Reporting functions
# ---------------------------------------------------------------------------
def get_daily_sales(report_date: date, store_id: int = 1) -> schemas.DailySalesReport:
    """Return sales totals for a single day for store_id."""
    start_utc, end_utc = _get_period_bounds(date_=report_date)
    with get_db_context() as db:
        stmt = (
            select(
                func.count(models.Bill.id),
                func.coalesce(func.sum(models.Bill.subtotal), Decimal('0')),
                func.coalesce(func.sum(models.Bill.taxable_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.cgst_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.sgst_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.tax_total), Decimal('0')),
                func.coalesce(func.sum(models.Bill.rounding_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.grand_total), Decimal('0')),
            )
            .where(models.Bill.store_id == store_id)
            .where(models.Bill.status == "FINALIZED")
            .where(models.Bill.created_at >= start_utc)
            .where(models.Bill.created_at < end_utc)
        )
        result = db.execute(stmt).first()
        if result is None:
            raise ReportGenerationError("Failed to fetch daily sales.")
        (
            bill_count,
            subtotal,
            taxable_amount,
            cgst_amount,
            sgst_amount,
            tax_total,
            rounding_amount,
            grand_total,
        ) = result
        return schemas.DailySalesReport(
            period=schemas.Period(start=report_date.isoformat(), end=report_date.isoformat()),
            bill_count=bill_count or 0,
            subtotal=subtotal,
            taxable_amount=taxable_amount,
            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,
            tax_total=tax_total,
            rounding_amount=rounding_amount,
            grand_total=grand_total,
        )

def get_sales_summary(start_date: date, end_date: date, store_id: int = 1) -> schemas.SalesSummaryReport:
    """Aggregate sales information for store_id."""
    start_utc, end_utc = _get_period_bounds(
        start=_local_midnight(start_date), end=_local_midnight(end_date)
    )
    with get_db_context() as db:
        stmt = (
            select(
                func.count(models.Bill.id),
                func.coalesce(func.sum(models.Bill.taxable_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.cgst_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.sgst_amount), Decimal('0')),
                func.coalesce(func.sum(models.Bill.tax_total), Decimal('0')),
                func.coalesce(func.sum(models.Bill.grand_total), Decimal('0')),
                func.coalesce(func.avg(models.Bill.grand_total), Decimal('0')),
                func.max(models.Bill.grand_total),
                func.min(models.Bill.grand_total),
            )
            .where(models.Bill.store_id == store_id)
            .where(models.Bill.status == "FINALIZED")
            .where(models.Bill.created_at >= start_utc)
            .where(models.Bill.created_at < end_utc)
        )
        result = db.execute(stmt).first()
        if result is None:
            raise ReportGenerationError("Failed to fetch sales summary.")
        (
            total_bills,
            total_taxable_amount,
            total_cgst,
            total_sgst,
            total_tax,
            total_sales,
            avg_bill_value,
            highest_bill_value,
            lowest_bill_value,
        ) = result
        return schemas.SalesSummaryReport(
            period=schemas.Period(start=start_date.isoformat(), end=end_date.isoformat()),
            total_bills=total_bills or 0,
            total_taxable_amount=total_taxable_amount,
            total_cgst=total_cgst,
            total_sgst=total_sgst,
            total_tax=total_tax,
            total_sales=total_sales,
            average_bill_value=avg_bill_value or Decimal('0'),
            highest_bill_value=highest_bill_value or Decimal('0'),
            lowest_bill_value=lowest_bill_value or Decimal('0'),
        )

def get_payment_breakdown(start_date: date, end_date: date, store_id: int = 1) -> schemas.PaymentBreakdownReport:
    """Return payment totals per method for store_id."""
    start_utc, end_utc = _get_period_bounds(
        start=_local_midnight(start_date), end=_local_midnight(end_date)
    )
    with get_db_context() as db:
        stmt = (
            select(
                models.Bill.payment_method,
                func.coalesce(func.sum(models.Bill.grand_total), Decimal('0')),
            )
            .where(models.Bill.store_id == store_id)
            .where(models.Bill.status == "FINALIZED")
            .where(models.Bill.created_at >= start_utc)
            .where(models.Bill.created_at < end_utc)
            .group_by(models.Bill.payment_method)
        )
        rows = db.execute(stmt).all()
        breakdown = {method: amount for method, amount in rows}
        total = sum(breakdown.values(), Decimal('0'))
        for method in ["CASH", "UPI", "CARD", "KHATA"]:
            breakdown.setdefault(method, Decimal('0'))
        summary = get_sales_summary(start_date, end_date, store_id=store_id)
        inconsistency = (
            f"Payment totals ({total}) do not match sales total ({summary.total_sales})"
            if total != summary.total_sales
            else None
        )
        return schemas.PaymentBreakdownReport(
            period=schemas.Period(start=start_date.isoformat(), end=end_date.isoformat()),
            cash=breakdown["CASH"],
            upi=breakdown["UPI"],
            card=breakdown["CARD"],
            khata=breakdown["KHATA"],
            total=total,
            inconsistency=inconsistency,
        )

def get_top_products(
    start_date: date,
    end_date: date,
    limit: int = 10,
    by: Literal["quantity", "revenue"] = "quantity",
    store_id: int = 1,
) -> List[schemas.TopProductDTO]:
    if limit <= 0:
        raise InvalidLimitError("limit must be a positive integer")
    start_utc, end_utc = _get_period_bounds(
        start=_local_midnight(start_date), end=_local_midnight(end_date)
    )
    with get_db_context() as db:
        subq = (
            select(
                models.BillItem.product_id,
                func.sum(models.BillItem.quantity).label("total_qty"),
                func.sum(models.BillItem.line_total).label("total_revenue"),
            )
            .join(models.Bill, models.Bill.id == models.BillItem.bill_id)
            .where(models.Bill.store_id == store_id)
            .where(models.Bill.status == "FINALIZED")
            .where(models.Bill.created_at >= start_utc)
            .where(models.Bill.created_at < end_utc)
            .group_by(models.BillItem.product_id)
        ).subquery()
        order_col = subq.c.total_qty if by == "quantity" else subq.c.total_revenue
        stmt = (
            select(
                models.Product.id,
                models.Product.name,
                subq.c.total_qty,
                subq.c.total_revenue,
            )
            .join(subq, models.Product.id == subq.c.product_id)
            .where(models.Product.store_id == store_id)
            .order_by(order_col.desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        result: List[schemas.TopProductDTO] = []
        for pid, name, qty, revenue in rows:
            result.append(
                schemas.TopProductDTO(
                    product_id=pid,
                    product_name=name,
                    quantity_sold=qty,
                    sales_value=revenue,
                )
            )
        return result

def get_gst_summary(start_date: date, end_date: date, store_id: int = 1) -> schemas.GstSummaryReport:
    start_utc, end_utc = _get_period_bounds(
        start=_local_midnight(start_date), end=_local_midnight(end_date)
    )
    with get_db_context() as db:
        stmt = (
            select(
                models.BillItem.gst_rate,
                func.sum(models.BillItem.taxable_amount).label("taxable"),
                func.sum(models.BillItem.cgst).label("cgst"),
                func.sum(models.BillItem.sgst).label("sgst"),
                func.sum(models.BillItem.tax_amount).label("gst_total"),
            )
            .join(models.Bill, models.Bill.id == models.BillItem.bill_id)
            .where(models.Bill.store_id == store_id)
            .where(models.Bill.status == "FINALIZED")
            .where(models.Bill.created_at >= start_utc)
            .where(models.Bill.created_at < end_utc)
            .group_by(models.BillItem.gst_rate)
        )
        rows = db.execute(stmt).all()
        slabs = []
        total_taxable = Decimal('0')
        total_cgst = Decimal('0')
        total_sgst = Decimal('0')
        total_gst = Decimal('0')
        for rate, taxable, cgst, sgst, gst_total in rows:
            slabs.append(
                schemas.GstSlab(
                    gst_rate=rate,
                    taxable_amount=taxable,
                    cgst_amount=cgst,
                    sgst_amount=sgst,
                    total_gst=gst_total,
                )
            )
            total_taxable += taxable
            total_cgst += cgst
            total_sgst += sgst
            total_gst += gst_total
        return schemas.GstSummaryReport(
            period=schemas.Period(start=start_date.isoformat(), end=end_date.isoformat()),
            total_taxable_amount=total_taxable,
            total_cgst=total_cgst,
            total_sgst=total_sgst,
            total_gst=total_gst,
            slabs=slabs,
        )

def get_stock_health(store_id: int = 1) -> schemas.StockHealthReport:
    with get_db_context() as db:
        stmt_all = select(models.Product).where(models.Product.store_id == store_id)
        products = db.execute(stmt_all).scalars().all()
        in_stock = []
        low_stock = []
        out_of_stock = []
        reorder = []
        for p in products:
            if p.stock_quantity == Decimal('0'):
                out_of_stock.append(p)
                status = schemas.StockStatus.OUT_OF_STOCK
            elif p.stock_quantity <= p.reorder_level:
                low_stock.append(p)
                status = schemas.StockStatus.LOW_STOCK
            else:
                in_stock.append(p)
                status = schemas.StockStatus.IN_STOCK
            if status in (schemas.StockStatus.LOW_STOCK, schemas.StockStatus.OUT_OF_STOCK):
                shortage = max(p.reorder_level - p.stock_quantity, Decimal('0'))
                reorder.append(
                    schemas.ReorderCandidate(
                        product_id=p.id,
                        product_name=p.name,
                        current_quantity=p.stock_quantity,
                        reorder_level=p.reorder_level,
                        unit=p.unit,
                        shortage_amount=shortage,
                    )
                )
        return schemas.StockHealthReport(
            in_stock=[schemas.StockStatusDTO.from_orm(p) for p in in_stock],
            low_stock=[schemas.StockStatusDTO.from_orm(p) for p in low_stock],
            out_of_stock=[schemas.StockStatusDTO.from_orm(p) for p in out_of_stock],
            reorder_candidates=reorder,
        )

def daily_close(report_date: date, store_id: int = 1) -> schemas.DailyCloseReport:
    """Generate a comprehensive daily-close report for store_id (read-only)."""
    daily = get_daily_sales(report_date, store_id=store_id)
    start = report_date
    end = report_date + timedelta(days=1)
    summary = get_sales_summary(start, end, store_id=store_id)
    payments = get_payment_breakdown(start, end, store_id=store_id)
    top_products = get_top_products(start, end, limit=5, store_id=store_id)
    stock = get_stock_health(store_id=store_id)
    return schemas.DailyCloseReport(
        period=schemas.Period(start=report_date.isoformat(), end=report_date.isoformat()),
        daily_sales=daily,
        sales_summary=summary,
        payment_breakdown=payments,
        top_products=top_products,
        stock_health=stock,
    )

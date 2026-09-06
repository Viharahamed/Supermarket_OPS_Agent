from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    Numeric,
    Boolean,
    ForeignKey,
    DateTime,
    Integer,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_product_stock_quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="piece")
    pack_size: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("1.00"))
    is_loose: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2, asdecimal=True), default=Decimal("0.00"))
    hsn_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    stock_movements: Mapped[List["StockMovement"]] = relationship(
        "StockMovement", back_populates="product", cascade="all, delete-orphan"
    )
    bill_items: Mapped[List["BillItem"]] = relationship("BillItem", back_populates="product")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ADDITION, SALE, ADJUSTMENT, RETURN
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    stock_after: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True, nullable=True)
    khata_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    bills: Mapped[List["Bill"]] = relationship("Bill", back_populates="customer")
    khata_transactions: Mapped[List["KhataTransaction"]] = relationship(
        "KhataTransaction", back_populates="customer", cascade="all, delete-orphan"
    )


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)  # DRAFT, FINALIZED, CANCELLED
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    payment_method: Mapped[str] = mapped_column(String(50), default="PENDING")  # CASH, UPI, KHATA, SPLIT, PENDING
    payment_status: Mapped[str] = mapped_column(String(50), default="UNPAID")  # PAID, UNPAID, PARTIAL
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    rounding_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="bills")
    items: Mapped[List["BillItem"]] = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")
    khata_transactions: Mapped[List["KhataTransaction"]] = relationship("KhataTransaction", back_populates="bill")


class BillItem(Base):
    __tablename__ = "bill_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2, asdecimal=True), nullable=False)
    hsn_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    cgst: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    sgst: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    bill: Mapped["Bill"] = relationship("Bill", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="bill_items")


class KhataTransaction(Base):
    __tablename__ = "khata_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    bill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CREDIT_SALE, PAYMENT, ADJUSTMENT
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="khata_transactions")
    bill: Mapped[Optional["Bill"]] = relationship("Bill", back_populates="khata_transactions")


class OwnerPreference(Base):
    __tablename__ = "owner_preferences"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    history_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

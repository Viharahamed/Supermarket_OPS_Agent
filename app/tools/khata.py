# app/tools/khata.py
"""Tool handlers for customer khata (ledger) actions with store_id context."""

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.db.models import Customer, KhataTransaction
from app.exceptions import CustomerNotFoundError
from app.tools.schemas import (
    FindCustomerInput,
    CreateCustomerInput,
    AddCreditInput,
    RecordPaymentInput,
    GetKhataBalanceInput,
    GetKhataHistoryInput,
)


def _extract_store_id(context: Optional[Any]) -> int:
    if context and hasattr(context, "principal") and context.principal:
        return context.principal.store_id
    return 1


def _customer_to_dict(c: Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "khata_balance": str(c.khata_balance),
        "created_at": str(c.created_at),
    }


def _txn_to_dict(t: KhataTransaction) -> dict:
    return {
        "id": t.id,
        "customer_id": t.customer_id,
        "bill_id": t.bill_id,
        "transaction_type": t.transaction_type,
        "amount": str(t.amount),
        "balance_after": str(t.balance_after),
        "created_at": str(t.created_at),
    }


import re


def _normalize_customer_query(raw_query: str) -> str:
    """Normalize customer query string by trimming, stripping punctuation, possessives, and noise words."""
    if not raw_query:
        return ""
    q = raw_query.strip().lower()
    # Remove common trailing noise words like "credit", "balance", "khata", "account", "ledger"
    q = re.sub(r"\b(credit|balance|khata|account|ledger)\b", "", q, flags=re.IGNORECASE).strip()
    # Remove possessive endings like 's or ' or ’s
    q = re.sub(r"['’]s?$", "", q, flags=re.IGNORECASE).strip()
    # Strip non-alphanumeric trailing/leading characters except space
    q = re.sub(r"^[^\w]+|[^\w]+$", "", q).strip()
    # Collapse multiple spaces
    q = re.sub(r"\s+", " ", q)
    return q


def find_customer(inp: FindCustomerInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    raw_q = inp.query or ""
    norm_q = _normalize_customer_query(raw_q)

    with get_db_context() as db:
        customers = db.query(Customer).filter(Customer.store_id == store_id).all()
        matches = []
        for c in customers:
            c_name = (c.name or "").strip().lower()
            c_phone = (c.phone or "").strip().lower()
            c_name_norm = re.sub(r"\s+", " ", c_name)

            if norm_q and (
                norm_q == c_name_norm
                or norm_q == c_phone
                or norm_q in c_name_norm
                or norm_q in c_phone
                or c_name_norm in norm_q
            ):
                matches.append(c)
            elif raw_q.lower().strip() and (raw_q.lower().strip() in c_name_norm or raw_q.lower().strip() in c_phone):
                matches.append(c)

        result_list = [_customer_to_dict(c) for c in matches]
        count = len(result_list)

    return {"customers": result_list, "count": count}


def create_customer(inp: CreateCustomerInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        customer = Customer(
            store_id=store_id,
            name=inp.name,
            phone=inp.phone,
            khata_balance=Decimal("0.00"),
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return _customer_to_dict(customer)


def add_credit(inp: AddCreditInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id, Customer.store_id == store_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        customer.khata_balance += inp.amount
        txn = KhataTransaction(
            store_id=store_id,
            customer_id=customer.id,
            transaction_type="CREDIT",
            amount=inp.amount,
            balance_after=customer.khata_balance,
            notes=inp.description,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return _txn_to_dict(txn)


def record_payment(inp: RecordPaymentInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id, Customer.store_id == store_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        customer.khata_balance -= inp.amount
        txn = KhataTransaction(
            store_id=store_id,
            customer_id=customer.id,
            transaction_type="PAYMENT",
            amount=inp.amount,
            balance_after=customer.khata_balance,
            notes=inp.description,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return _txn_to_dict(txn)


def get_khata_balance(inp: GetKhataBalanceInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id, Customer.store_id == store_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "khata_balance": str(customer.khata_balance),
        }


def get_khata_history(inp: GetKhataHistoryInput, context: Optional[Any] = None) -> dict:
    store_id = _extract_store_id(context)
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id, Customer.store_id == store_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        query = (
            db.query(KhataTransaction)
            .filter(KhataTransaction.customer_id == inp.customer_id, KhataTransaction.store_id == store_id)
            .order_by(KhataTransaction.created_at.desc())
        )
        if inp.limit:
            query = query.limit(inp.limit)
        transactions = query.all()
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "transactions": [_txn_to_dict(t) for t in transactions],
        }

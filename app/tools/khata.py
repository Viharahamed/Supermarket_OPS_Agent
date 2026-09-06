# app/tools/khata.py
"""Tool handlers for customer khata (ledger) actions.

These functions accept validated Pydantic input models from
``app.tools.schemas`` and interact with the Customer / KhataTransaction
database models directly, since there is no dedicated khata service yet.
"""

from decimal import Decimal
from typing import Optional

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


def find_customer(inp: FindCustomerInput) -> dict:
    with get_db_context() as db:
        q = inp.query.lower()
        customers = db.query(Customer).all()
        matches = [
            c for c in customers
            if q in (c.name or "").lower() or q in (c.phone or "").lower()
        ]
    return {"customers": [_customer_to_dict(c) for c in matches], "count": len(matches)}


def create_customer(inp: CreateCustomerInput) -> dict:
    with get_db_context() as db:
        customer = Customer(
            name=inp.name,
            phone=inp.phone,
            khata_balance=Decimal("0.00"),
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return _customer_to_dict(customer)


def add_credit(inp: AddCreditInput) -> dict:
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        customer.khata_balance += inp.amount
        txn = KhataTransaction(
            customer_id=customer.id,
            transaction_type="CREDIT",
            amount=inp.amount,
            balance_after=customer.khata_balance,
            description=inp.description,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return _txn_to_dict(txn)


def record_payment(inp: RecordPaymentInput) -> dict:
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        customer.khata_balance -= inp.amount
        txn = KhataTransaction(
            customer_id=customer.id,
            transaction_type="PAYMENT",
            amount=inp.amount,
            balance_after=customer.khata_balance,
            description=inp.description,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        return _txn_to_dict(txn)


def get_khata_balance(inp: GetKhataBalanceInput) -> dict:
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "khata_balance": str(customer.khata_balance),
        }


def get_khata_history(inp: GetKhataHistoryInput) -> dict:
    with get_db_context() as db:
        customer = db.query(Customer).filter(Customer.id == inp.customer_id).first()
        if not customer:
            raise CustomerNotFoundError(inp.customer_id)
        query = (
            db.query(KhataTransaction)
            .filter(KhataTransaction.customer_id == inp.customer_id)
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

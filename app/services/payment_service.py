from decimal import Decimal
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.db.models import Bill, Customer, KhataTransaction, StockMovement, Product
from app.exceptions import (
    DatabaseLockedError,
    InvalidPaymentMethodError,
    InsufficientKhataBalanceError,
    PaymentAlreadyProcessedError,
    InvalidSplitPaymentError,
    BillNotFoundError,
    CustomerNotFoundError,
    BillAlreadyFinalizedError,
)

VALID_PAYMENT_METHODS = {"CASH", "UPI", "KHATA", "SPLIT"}


def validate_payment_method(method: str) -> None:
    """Ensure the supplied payment method is supported.
    Raises:
        InvalidPaymentMethodError: if method is not in VALID_PAYMENT_METHODS.
    """
    if method.upper() not in VALID_PAYMENT_METHODS:
        raise InvalidPaymentMethodError(f"Unsupported payment method: {method}")


def _apply_khata_payment(
    session: Session,
    customer: Customer,
    amount: Decimal,
    min_balance: Decimal = Decimal("0.00"),
    overdraft_limit: Decimal = Decimal("-500.00"),
) -> None:
    """Adjust a customer's khata_balance respecting business rules.
    - Balance after payment must be >= `min_balance` (default 0).
    - Balance may go negative but not below `overdraft_limit`.
    Raises:
        InsufficientKhataBalanceError: if resulting balance violates limits.
    """
    new_balance = customer.khata_balance - amount
    if new_balance < overdraft_limit:
        raise InsufficientKhataBalanceError(
            requested=str(amount),
            available=str(customer.khata_balance),
            limit=str(overdraft_limit),
        )
    if new_balance < min_balance:
        raise InsufficientKhataBalanceError(
            requested=str(amount),
            available=str(customer.khata_balance),
            limit=str(min_balance),
        )
    customer.khata_balance = new_balance
    session.add(customer)


def _record_khata_transaction(
    session: Session,
    customer: Customer,
    bill: Bill,
    amount: Decimal,
    idempotency_key: Optional[str] = None,
) -> KhataTransaction:
    """Create a PAYMENT type KhataTransaction and persist it."""
    txn = KhataTransaction(
        customer_id=customer.id,
        bill_id=bill.id,
        transaction_type="PAYMENT",
        amount=amount,
        balance_after=customer.khata_balance,
        idempotency_key=idempotency_key,
    )
    session.add(txn)
    return txn


from app.db.retry_utils import retry_on_lock
import time

@retry_on_lock(max_retries=3, backoff_factor=0.5)
def process_payment(
    session: Session,
    bill_id: int,
    method: str,
    amount: Decimal,
    *,
    split_components: Optional[List[Tuple[str, Decimal]]] = None,
    idempotency_key: Optional[str] = None,
    min_khata_balance: Decimal = Decimal("0.00"),
    khata_overdraft_limit: Decimal = Decimal("-500.00"),
) -> Bill:
    """Core payment handling.

    Supports full, partial, and split payments. For KHATA payments it validates
    minimum balance and overdraft limits. Idempotent via `idempotency_key`.
    """
    validate_payment_method(method)

    # Begin atomic transaction
    with session.begin_nested():
        bill = session.query(Bill).filter_by(id=bill_id).first()
        if not bill:
            raise BillNotFoundError(bill_id)

        if bill.status != "DRAFT":
            raise BillAlreadyFinalizedError(bill_id)

        # Idempotency – if a bill with the same key already exists, return it.
        if idempotency_key:
            existing = (
                session.query(Bill)
                .filter_by(idempotency_key=idempotency_key)
                .first()
            )
            if existing:
                return existing

        # Split payment handling
        if method.upper() == "SPLIT":
            if not split_components:
                raise InvalidSplitPaymentError(
                    "Split components are required for SPLIT payment."
                )
            total = sum(comp[1] for comp in split_components)
            if total != amount:
                raise InvalidSplitPaymentError(
                    f"Split total {total} does not equal amount {amount}"
                )
            for sub_method, sub_amount in split_components:
                # Re‑use the same idempotency key for each sub‑payment
                process_payment(
                    session,
                    bill_id=bill_id,
                    method=sub_method,
                    amount=sub_amount,
                    idempotency_key=idempotency_key,
                    min_khata_balance=min_khata_balance,
                    khata_overdraft_limit=khata_overdraft_limit,
                )
            # After all components succeed, update status accordingly
            bill.payment_status = "PARTIAL" if amount < bill.grand_total else "PAID"
            bill.payment_method = "SPLIT"
            session.add(bill)
            return bill

        # Non‑split payments (CASH, UPI, KHATA)
        if method.upper() == "KHATA":
            if not bill.customer_id:
                raise InvalidPaymentMethodError(
                    "KHATA payment requires a linked customer on the bill."
                )
            customer = (
                session.query(Customer)
                .filter_by(id=bill.customer_id)
                .with_for_update()
                .first()
            )
            if not customer:
                raise CustomerNotFoundError(bill.customer_id)
            _apply_khata_payment(
                session,
                customer,
                amount,
                min_balance=min_khata_balance,
                overdraft_limit=khata_overdraft_limit,
            )
            _record_khata_transaction(
                session,
                customer,
                bill,
                amount,
                idempotency_key=idempotency_key,
            )

        # CASH and UPI need no extra ledger work

        # Update bill fields
        bill.payment_method = method.upper()
        bill.payment_status = "PAID" if amount == bill.grand_total else "PARTIAL"
        bill.idempotency_key = idempotency_key
        session.add(bill)
        # session.commit() is handled by the outer transaction block
        session.flush()
        return bill

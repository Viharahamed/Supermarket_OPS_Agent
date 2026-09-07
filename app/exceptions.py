"""Domain-specific exception hierarchy for Kirana AI Agent."""

class KiranaException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, code: str = "GENERIC_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

class ApplicationError(KiranaException):
    """Base class for all application‑specific errors with a stable error_code.
    Existing code (e.g., IdempotencyConflictError) expects this name.
    """
    error_code: str = "APPLICATION_ERROR"

    def __init__(self, message: str = ""):
        super().__init__(message, code=self.error_code)


class InventoryError(KiranaException):
    """Base exception for inventory engine operations."""
    def __init__(self, message: str, code: str = "INVENTORY_ERROR"):
        super().__init__(message, code=code)


class ProductNotFoundError(InventoryError):
    def __init__(self, product_id: int):
        super().__init__(f"Product with ID '{product_id}' was not found.", code="PRODUCT_NOT_FOUND")
        self.product_id = product_id


class ProductInactiveError(InventoryError):
    def __init__(self, product_id: int):
        super().__init__(f"Product with ID '{product_id}' is inactive.", code="PRODUCT_INACTIVE")
        self.product_id = product_id


class InvalidQuantityError(InventoryError):
    def __init__(self, message: str = "Quantity must be greater than 0."):
        super().__init__(message, code="INVALID_QUANTITY")


class InvalidPriceError(InventoryError):
    def __init__(self, message: str = "Invalid price specified."):
        super().__init__(message, code="INVALID_PRICE")


class NegativeStockError(InventoryError):
    def __init__(self, current_stock: str, requested_change: str):
        super().__init__(
            f"Stock adjustment of {requested_change} would result in negative stock (current: {current_stock}).",
            code="NEGATIVE_STOCK"
        )


class InvalidAdjustmentError(InventoryError):
    def __init__(self, message: str = "Invalid stock adjustment operation."):
        super().__init__(message, code="INVALID_ADJUSTMENT")


class PricingError(KiranaException):
    """Base exception for pricing validation operations."""
    def __init__(self, message: str, code: str = "PRICING_ERROR"):
        super().__init__(message, code=code)


class PriceBelowCostError(PricingError):
    def __init__(self, selling_price: str, cost_price: str):
        super().__init__(
            f"Selling price ({selling_price}) cannot be below cost price ({cost_price}).",
            code="PRICE_BELOW_COST"
        )


class PriceAboveMRPError(PricingError):
    def __init__(self, selling_price: str, mrp: str):
        super().__init__(
            f"Selling price ({selling_price}) cannot exceed MRP ({mrp}).",
            code="PRICE_ABOVE_MRP"
        )


class GSTError(KiranaException):
    """Base exception for GST calculation operations."""
    def __init__(self, message: str, code: str = "GST_ERROR"):
        super().__init__(message, code=code)


class InvalidGSTRateError(GSTError):
    def __init__(self, gst_rate: str):
        super().__init__(
            f"Invalid GST rate specified: {gst_rate}. Must be a non-negative decimal (e.g. 0, 5, 12, 18).",
            code="INVALID_GST_RATE"
        )


class BillingError(KiranaException):
    """Base exception for billing engine operations."""
    def __init__(self, message: str, code: str = "BILLING_ERROR"):
        super().__init__(message, code=code)


class BillNotFoundError(BillingError):
    def __init__(self, bill_id: int):
        super().__init__(f"Bill with ID '{bill_id}' was not found.", code="BILL_NOT_FOUND")
        self.bill_id = bill_id


class BillNotDraftError(BillingError):
    def __init__(self, bill_id: int, current_status: str):
        super().__init__(
            f"Bill '{bill_id}' is not in DRAFT status (current status: '{current_status}').",
            code="BILL_NOT_DRAFT"
        )
        self.bill_id = bill_id
        self.current_status = current_status


class BillAlreadyFinalizedError(BillingError):
    def __init__(self, bill_id: int):
        super().__init__(
            f"Bill '{bill_id}' is already FINALIZED and cannot be modified.",
            code="BILL_ALREADY_FINALIZED"
        )
        self.bill_id = bill_id


class BillNotFinalizedError(BillingError):
    def __init__(self, bill_id: int, current_status: str = "DRAFT"):
        super().__init__(
            f"Cannot generate PDF invoice for bill '{bill_id}': Bill status is '{current_status}' (must be FINALIZED).",
            code="BILL_NOT_FINALIZED",
        )
        self.bill_id = bill_id
        self.current_status = current_status


class DocumentGenerationError(KiranaException):
    def __init__(self, message: str = "Document generation failed."):
        super().__init__(message, code="DOCUMENT_GENERATION_FAILED")


class DocumentNotFoundError(KiranaException):
    def __init__(self, file_path: str):
        super().__init__(f"Document file at '{file_path}' was not found.", code="DOCUMENT_NOT_FOUND")
        self.file_path = file_path


class EmptyBillError(BillingError):
    def __init__(self, bill_id: int):
        super().__init__(f"Cannot finalize empty bill '{bill_id}'.", code="EMPTY_BILL")
        self.bill_id = bill_id


class InsufficientStockError(BillingError):
    def __init__(self, product_name: str, requested: str, available: str):
        super().__init__(
            f"Insufficient stock for '{product_name}': requested {requested}, but only {available} available.",
            code="INSUFFICIENT_STOCK"
        )
        self.product_name = product_name
        self.requested = requested
        self.available = available

# Payment Engine Exceptions
class InvalidPaymentMethodError(KiranaException):
    def __init__(self, message: str = "Invalid payment method."):
        super().__init__(message, code="INVALID_PAYMENT_METHOD")

class InsufficientKhataBalanceError(KiranaException):
    def __init__(self, requested: str, available: str, limit: str):
        super().__init__(
            f"KHATA balance insufficient: requested {requested}, available {available}, limit {limit}",
            code="INSUFFICIENT_KHATA_BALANCE",
        )
        self.requested = requested
        self.available = available
        self.limit = limit

class PaymentAlreadyProcessedError(KiranaException):
    def __init__(self, message: str = "Payment has already been processed for this bill."):
        super().__init__(message, code="PAYMENT_ALREADY_PROCESSED")

class InvalidSplitPaymentError(KiranaException):
    def __init__(self, message: str = "Invalid split payment configuration."):
        super().__init__(message, code="INVALID_SPLIT_PAYMENT")

class CustomerNotFoundError(KiranaException):
    def __init__(self, customer_id: int):
        super().__init__(f"Customer with ID '{customer_id}' not found.", code="CUSTOMER_NOT_FOUND")
        self.customer_id = customer_id

# ---------------------------------------------------------------------------
# Reporting specific exceptions
# ---------------------------------------------------------------------------

class InvalidDateError(KiranaException):
    def __init__(self, message: str = "Invalid date supplied."):
        super().__init__(message, code="INVALID_DATE")

class InvalidDateRangeError(KiranaException):
    def __init__(self, message: str = "Invalid date range supplied."):
        super().__init__(message, code="INVALID_DATE_RANGE")

class InvalidLimitError(KiranaException):
    def __init__(self, message: str = "Invalid limit supplied."):
        super().__init__(message, code="INVALID_LIMIT")

class ReportGenerationError(KiranaException):
    def __init__(self, message: str = "Error generating report."):
        super().__init__(message, code="REPORT_GENERATION_ERROR")

class DataInconsistencyError(KiranaException):
    def __init__(self, message: str = "Data inconsistency detected."):
        super().__init__(message, code="DATA_INCONSISTENCY")

# Concurrency & Idempotency Exceptions

class IdempotencyConflictError(ApplicationError):
    """Raised when an idempotency key conflict occurs."""
    error_code = "IDEMPOTENCY_CONFLICT"

    def __init__(self, message: str = "Idempotency key conflict."):
        super().__init__(message)

class DatabaseLockedError(ApplicationError):
    """Raised when SQLite reports a locked database."""
    error_code = "DATABASE_LOCKED"

    def __init__(self, message: str = "Database is locked (SQLite busy timeout)."):
        super().__init__(message)

class TransactionFailedError(ApplicationError):
    """Raised when a transaction fails and is rolled back."""
    error_code = "TRANSACTION_FAILED"

    def __init__(self, message: str = "Transaction failed and was rolled back."):
        super().__init__(message)


# ---------------------------------------------------------------------------
# LLM Provider & Model specific exceptions
# ---------------------------------------------------------------------------

class LLMProviderError(KiranaException):
    """Base exception for all LLM provider interactions."""
    def __init__(self, message: str, code: str = "LLM_PROVIDER_ERROR"):
        super().__init__(message, code=code)


class LLMAuthenticationError(LLMProviderError):
    """Raised when LLM provider authentication fails (e.g. missing or invalid API key)."""
    def __init__(self, message: str = "LLM provider authentication failed."):
        super().__init__(message, code="LLM_AUTHENTICATION_ERROR")


class LLMUnavailableError(LLMProviderError):
    """Raised when LLM provider service cannot be reached."""
    def __init__(self, message: str = "LLM provider service is unavailable.", code: str = "LLM_UNAVAILABLE"):
        super().__init__(message, code=code)


class LLMTimeoutError(LLMProviderError):
    """Raised when request to LLM provider times out."""
    def __init__(self, message: str = "LLM provider request timed out.", code: str = "LLM_TIMEOUT"):
        super().__init__(message, code=code)


class OllamaError(LLMProviderError):
    """Base exception for Ollama/Model interactions."""
    def __init__(self, message: str, code: str = "OLLAMA_ERROR"):
        super().__init__(message, code=code)


class OllamaUnavailableError(OllamaError, LLMUnavailableError):
    """Raised when Ollama service cannot be reached."""
    def __init__(self, message: str = "Ollama service is unavailable at configured host."):
        super().__init__(message, code="OLLAMA_UNAVAILABLE")


class OllamaTimeoutError(OllamaError, LLMTimeoutError):
    """Raised when request to Ollama times out."""
    def __init__(self, message: str = "Ollama request timed out."):
        super().__init__(message, code="OLLAMA_TIMEOUT")


class ModelNotFoundError(LLMProviderError):
    """Raised when specified model is not found in provider."""
    def __init__(self, model_name: str):
        super().__init__(f"Model '{model_name}' was not found.", code="MODEL_NOT_FOUND")
        self.model_name = model_name


class InvalidModelResponseError(LLMProviderError):
    """Raised when model returns malformed response or invalid action schema."""
    def __init__(self, message: str = "Model returned invalid action schema."):
        super().__init__(message, code="INVALID_MODEL_RESPONSE")


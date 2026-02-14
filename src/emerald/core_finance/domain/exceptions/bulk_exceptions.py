from emerald.shared_kernel.domain.exceptions import (
    InvalidValueError,
    InvariantViolationError,
)


class BulkLimitExceededError(InvariantViolationError):
    """More than the maximum number of items in a bulk request."""

    def __init__(
        self,
        message: str = "Bulk request exceeds the maximum of 1000 items",
        code: str = "BULK_LIMIT_EXCEEDED",
    ) -> None:
        super().__init__(message, code)


class EmptyBulkRequestError(InvariantViolationError):
    """Zero items in a bulk request."""

    def __init__(
        self,
        message: str = "Bulk request must contain at least one item",
        code: str = "EMPTY_BULK_REQUEST",
    ) -> None:
        super().__init__(message, code)


class EmptyBulkUpdateError(InvalidValueError):
    """No fields set in BulkUpdateFields (all _UNSET)."""

    def __init__(
        self,
        message: str = "At least one field must be set for bulk update",
        code: str = "EMPTY_BULK_UPDATE",
    ) -> None:
        super().__init__(message, code)

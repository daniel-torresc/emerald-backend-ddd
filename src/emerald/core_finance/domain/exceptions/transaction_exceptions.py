from emerald.shared_kernel.domain.exceptions import (
    ConflictError,
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)


class DuplicateExternalIdError(ConflictError):
    """External ID already exists within the same account."""

    def __init__(
        self,
        message: str = "Duplicate external ID",
        code: str = "DUPLICATE_EXTERNAL_ID",
    ) -> None:
        super().__init__(message, code)


class TransactionNotFoundError(NotFoundError):
    """Transaction not found in repository."""

    def __init__(
        self,
        message: str = "Transaction not found",
        code: str = "TRANSACTION_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)


class TransactionDeletedError(InvariantViolationError):
    """Update attempted on a soft-deleted transaction."""

    def __init__(
        self,
        message: str = "Transaction is deleted",
        code: str = "TRANSACTION_DELETED",
    ) -> None:
        super().__init__(message, code)


class EmptyDescriptionError(InvalidValueError):
    """Description is empty or whitespace-only."""

    def __init__(
        self,
        message: str = "Description cannot be empty",
        code: str = "EMPTY_DESCRIPTION",
    ) -> None:
        super().__init__(message, code)


class InvalidMerchantError(InvalidValueError):
    """Merchant string is invalid (empty, whitespace-only, or exceeds max length)."""

    def __init__(
        self,
        message: str = "Invalid merchant",
        code: str = "INVALID_MERCHANT",
    ) -> None:
        super().__init__(message, code)


class InvalidCommentsError(InvalidValueError):
    """Comments string is invalid (empty, whitespace-only, or exceeds max length)."""

    def __init__(
        self,
        message: str = "Invalid comments",
        code: str = "INVALID_COMMENTS",
    ) -> None:
        super().__init__(message, code)


class ParentAccountDeletedError(InvariantViolationError):
    """Recovery attempted when parent account is deleted."""

    def __init__(
        self,
        message: str = "Parent account is deleted",
        code: str = "PARENT_ACCOUNT_DELETED",
    ) -> None:
        super().__init__(message, code)

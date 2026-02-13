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


# -- Split-related exceptions (Spec 010) --------------------------------------


class MinimumSplitsRequiredError(InvariantViolationError):
    """Fewer than the minimum number of splits were provided."""

    def __init__(
        self,
        message: str = "At least 2 splits are required",
        code: str = "MINIMUM_SPLITS_REQUIRED",
    ) -> None:
        super().__init__(message, code)


class MaxSplitsExceededError(InvariantViolationError):
    """More than the maximum number of splits were provided."""

    def __init__(
        self,
        message: str = "Maximum 50 splits per transaction",
        code: str = "MAX_SPLITS_EXCEEDED",
    ) -> None:
        super().__init__(message, code)


class SplitAmountMismatchError(InvariantViolationError):
    """Split amounts do not sum to the parent transaction amount."""

    def __init__(
        self,
        message: str = "Split amounts do not sum to parent amount",
        code: str = "SPLIT_AMOUNT_MISMATCH",
        *,
        expected: str = "",
        actual: str = "",
    ) -> None:
        if expected and actual:
            message = (
                f"Split amounts do not sum to parent amount: expected {expected}, got {actual}"
            )
        super().__init__(message, code)


class CannotSplitChildError(InvariantViolationError):
    """Cannot split a transaction that is itself a split child."""

    def __init__(
        self,
        message: str = "Cannot split a split child transaction",
        code: str = "CANNOT_SPLIT_CHILD",
    ) -> None:
        super().__init__(message, code)


class AlreadySplitError(InvariantViolationError):
    """Transaction is already split into children."""

    def __init__(
        self,
        message: str = "Transaction is already split",
        code: str = "ALREADY_SPLIT",
    ) -> None:
        super().__init__(message, code)


class NotSplitParentError(InvariantViolationError):
    """Operation requires a split parent but transaction is not split."""

    def __init__(
        self,
        message: str = "Transaction is not a split parent",
        code: str = "NOT_SPLIT_PARENT",
    ) -> None:
        super().__init__(message, code)


class ParentDeletedError(InvariantViolationError):
    """Cannot recover a split child when its parent is deleted."""

    def __init__(
        self,
        message: str = "Parent transaction is deleted",
        code: str = "PARENT_DELETED",
    ) -> None:
        super().__init__(message, code)

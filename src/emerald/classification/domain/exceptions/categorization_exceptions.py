from emerald.shared_kernel.domain.exceptions import NotFoundError


class TransactionNotActiveError(NotFoundError):
    """Transaction does not exist or is soft-deleted."""

    def __init__(
        self,
        message: str = "Transaction is not active",
        code: str = "TRANSACTION_NOT_ACTIVE",
    ) -> None:
        super().__init__(message, code)


class AssignmentNotFoundError(NotFoundError):
    """No assignment for the given transaction + taxonomy pair."""

    def __init__(
        self,
        message: str = "Assignment not found",
        code: str = "ASSIGNMENT_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)

from emerald.shared_kernel.domain.exceptions import (
    DomainError,
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)


class EmptyProviderNameError(InvalidValueError):
    """Provider name is empty or blank."""

    def __init__(
        self,
        message: str = "Provider name must not be empty",
        code: str = "EMPTY_PROVIDER_NAME",
    ) -> None:
        super().__init__(message, code)


class ProviderNameTooLongError(InvalidValueError):
    """Provider name exceeds maximum length."""

    def __init__(
        self,
        message: str = "Provider name is too long",
        code: str = "PROVIDER_NAME_TOO_LONG",
    ) -> None:
        super().__init__(message, code)


class InvalidNormalizedTransactionError(InvalidValueError):
    """Normalized transaction data is invalid."""

    def __init__(
        self,
        message: str = "Invalid normalized transaction",
        code: str = "INVALID_NORMALIZED_TRANSACTION",
    ) -> None:
        super().__init__(message, code)


class InvalidProviderCredentialsError(InvalidValueError):
    """Empty credentials token."""

    def __init__(
        self,
        message: str = "Provider credentials token must not be empty",
        code: str = "INVALID_PROVIDER_CREDENTIALS",
    ) -> None:
        super().__init__(message, code)


class InvalidSyncFrequencyError(InvalidValueError):
    """Sync frequency outside allowed range."""

    def __init__(
        self,
        message: str = "Sync frequency is outside allowed range",
        code: str = "INVALID_SYNC_FREQUENCY",
    ) -> None:
        super().__init__(message, code)


class ConnectionNotActiveError(InvariantViolationError):
    """Sync on non-ACTIVE connection."""

    def __init__(
        self,
        message: str = "Connection is not active",
        code: str = "CONNECTION_NOT_ACTIVE",
    ) -> None:
        super().__init__(message, code)


class InvalidConnectionStateError(InvariantViolationError):
    """Invalid state transition."""

    def __init__(
        self,
        message: str = "Invalid connection state transition",
        code: str = "INVALID_CONNECTION_STATE",
    ) -> None:
        super().__init__(message, code)


class DuplicateConnectionError(InvariantViolationError):
    """Same account + provider already has a connection."""

    def __init__(
        self,
        message: str = "A connection already exists for this account and provider",
        code: str = "DUPLICATE_CONNECTION",
    ) -> None:
        super().__init__(message, code)


class SyncAlreadyInProgressError(InvariantViolationError):
    """Starting sync while one is already running."""

    def __init__(
        self,
        message: str = "A sync is already in progress for this connection",
        code: str = "SYNC_ALREADY_IN_PROGRESS",
    ) -> None:
        super().__init__(message, code)


class SyncAlreadyCompletedError(InvariantViolationError):
    """Completing an already-finished sync."""

    def __init__(
        self,
        message: str = "Sync has already been completed",
        code: str = "SYNC_ALREADY_COMPLETED",
    ) -> None:
        super().__init__(message, code)


class InvalidPendingStateError(InvariantViolationError):
    """Invalid pending transaction state transition."""

    def __init__(
        self,
        message: str = "Invalid pending transaction state transition",
        code: str = "INVALID_PENDING_STATE",
    ) -> None:
        super().__init__(message, code)


class PendingTransactionNotFoundError(NotFoundError):
    """Pending transaction not found."""

    def __init__(
        self,
        message: str = "Pending transaction not found",
        code: str = "PENDING_TRANSACTION_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)


class BankConnectionNotFoundError(NotFoundError):
    """Bank connection not found."""

    def __init__(
        self,
        message: str = "Bank connection not found",
        code: str = "BANK_CONNECTION_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)


class SyncHistoryNotFoundError(NotFoundError):
    """Sync history not found."""

    def __init__(
        self,
        message: str = "Sync history not found",
        code: str = "SYNC_HISTORY_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)


class ProviderAuthError(DomainError):
    """Provider credentials expired or invalid."""

    def __init__(
        self,
        message: str = "Provider authentication failed",
        code: str = "PROVIDER_AUTH_ERROR",
    ) -> None:
        super().__init__(message, code)


class ProviderError(DomainError):
    """General provider failure."""

    def __init__(
        self,
        message: str = "Provider error",
        code: str = "PROVIDER_ERROR",
    ) -> None:
        super().__init__(message, code)

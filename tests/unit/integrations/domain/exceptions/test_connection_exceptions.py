"""Tests for bank connection domain exceptions."""

from emerald.integrations.domain.exceptions.connection_exceptions import (
    BankConnectionNotFoundError,
    ConnectionNotActiveError,
    DuplicateConnectionError,
    EmptyProviderNameError,
    InvalidConnectionStateError,
    InvalidNormalizedTransactionError,
    InvalidPendingStateError,
    InvalidProviderCredentialsError,
    InvalidSyncFrequencyError,
    PendingTransactionNotFoundError,
    ProviderAuthError,
    ProviderError,
    ProviderNameTooLongError,
    SyncAlreadyCompletedError,
    SyncAlreadyInProgressError,
    SyncHistoryNotFoundError,
)
from emerald.shared_kernel.domain.exceptions import (
    DomainError,
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)


class TestInvalidValueErrors:
    """Exceptions extending InvalidValueError."""

    def test_empty_provider_name_error_code(self) -> None:
        err = EmptyProviderNameError()
        assert err.code == "EMPTY_PROVIDER_NAME"

    def test_empty_provider_name_error_base_class(self) -> None:
        assert issubclass(EmptyProviderNameError, InvalidValueError)

    def test_empty_provider_name_error_message(self) -> None:
        err = EmptyProviderNameError()
        assert str(err) == "Provider name must not be empty"

    def test_provider_name_too_long_error_code(self) -> None:
        err = ProviderNameTooLongError()
        assert err.code == "PROVIDER_NAME_TOO_LONG"

    def test_provider_name_too_long_error_base_class(self) -> None:
        assert issubclass(ProviderNameTooLongError, InvalidValueError)

    def test_invalid_normalized_transaction_error_code(self) -> None:
        err = InvalidNormalizedTransactionError()
        assert err.code == "INVALID_NORMALIZED_TRANSACTION"

    def test_invalid_normalized_transaction_error_base_class(self) -> None:
        assert issubclass(InvalidNormalizedTransactionError, InvalidValueError)

    def test_invalid_provider_credentials_error_code(self) -> None:
        err = InvalidProviderCredentialsError()
        assert err.code == "INVALID_PROVIDER_CREDENTIALS"

    def test_invalid_provider_credentials_error_base_class(self) -> None:
        assert issubclass(InvalidProviderCredentialsError, InvalidValueError)

    def test_invalid_sync_frequency_error_code(self) -> None:
        err = InvalidSyncFrequencyError()
        assert err.code == "INVALID_SYNC_FREQUENCY"

    def test_invalid_sync_frequency_error_base_class(self) -> None:
        assert issubclass(InvalidSyncFrequencyError, InvalidValueError)


class TestInvariantViolationErrors:
    """Exceptions extending InvariantViolationError."""

    def test_connection_not_active_error_code(self) -> None:
        err = ConnectionNotActiveError()
        assert err.code == "CONNECTION_NOT_ACTIVE"

    def test_connection_not_active_error_base_class(self) -> None:
        assert issubclass(ConnectionNotActiveError, InvariantViolationError)

    def test_invalid_connection_state_error_code(self) -> None:
        err = InvalidConnectionStateError()
        assert err.code == "INVALID_CONNECTION_STATE"

    def test_invalid_connection_state_error_base_class(self) -> None:
        assert issubclass(InvalidConnectionStateError, InvariantViolationError)

    def test_duplicate_connection_error_code(self) -> None:
        err = DuplicateConnectionError()
        assert err.code == "DUPLICATE_CONNECTION"

    def test_duplicate_connection_error_base_class(self) -> None:
        assert issubclass(DuplicateConnectionError, InvariantViolationError)

    def test_sync_already_in_progress_error_code(self) -> None:
        err = SyncAlreadyInProgressError()
        assert err.code == "SYNC_ALREADY_IN_PROGRESS"

    def test_sync_already_in_progress_error_base_class(self) -> None:
        assert issubclass(SyncAlreadyInProgressError, InvariantViolationError)

    def test_sync_already_completed_error_code(self) -> None:
        err = SyncAlreadyCompletedError()
        assert err.code == "SYNC_ALREADY_COMPLETED"

    def test_sync_already_completed_error_base_class(self) -> None:
        assert issubclass(SyncAlreadyCompletedError, InvariantViolationError)

    def test_invalid_pending_state_error_code(self) -> None:
        err = InvalidPendingStateError()
        assert err.code == "INVALID_PENDING_STATE"

    def test_invalid_pending_state_error_base_class(self) -> None:
        assert issubclass(InvalidPendingStateError, InvariantViolationError)


class TestNotFoundErrors:
    """Exceptions extending NotFoundError."""

    def test_pending_transaction_not_found_error_code(self) -> None:
        err = PendingTransactionNotFoundError()
        assert err.code == "PENDING_TRANSACTION_NOT_FOUND"

    def test_pending_transaction_not_found_error_base_class(self) -> None:
        assert issubclass(PendingTransactionNotFoundError, NotFoundError)

    def test_bank_connection_not_found_error_code(self) -> None:
        err = BankConnectionNotFoundError()
        assert err.code == "BANK_CONNECTION_NOT_FOUND"

    def test_bank_connection_not_found_error_base_class(self) -> None:
        assert issubclass(BankConnectionNotFoundError, NotFoundError)

    def test_sync_history_not_found_error_code(self) -> None:
        err = SyncHistoryNotFoundError()
        assert err.code == "SYNC_HISTORY_NOT_FOUND"

    def test_sync_history_not_found_error_base_class(self) -> None:
        assert issubclass(SyncHistoryNotFoundError, NotFoundError)


class TestDomainErrors:
    """Exceptions extending DomainError directly."""

    def test_provider_auth_error_code(self) -> None:
        err = ProviderAuthError()
        assert err.code == "PROVIDER_AUTH_ERROR"

    def test_provider_auth_error_base_class(self) -> None:
        assert issubclass(ProviderAuthError, DomainError)

    def test_provider_auth_error_message(self) -> None:
        err = ProviderAuthError()
        assert str(err) == "Provider authentication failed"

    def test_provider_error_code(self) -> None:
        err = ProviderError()
        assert err.code == "PROVIDER_ERROR"

    def test_provider_error_base_class(self) -> None:
        assert issubclass(ProviderError, DomainError)

    def test_provider_error_message(self) -> None:
        err = ProviderError()
        assert str(err) == "Provider error"


class TestCustomMessages:
    """All exceptions accept custom messages."""

    def test_empty_provider_name_custom_message(self) -> None:
        err = EmptyProviderNameError(message="custom msg")
        assert str(err) == "custom msg"

    def test_invalid_pending_state_custom_message(self) -> None:
        err = InvalidPendingStateError(message="bad state transition")
        assert str(err) == "bad state transition"

    def test_provider_auth_error_custom_message(self) -> None:
        err = ProviderAuthError(message="token expired")
        assert str(err) == "token expired"


class TestAllExceptionsCount:
    """Verify the expected number of exception classes."""

    ALL_EXCEPTIONS = [
        EmptyProviderNameError,
        ProviderNameTooLongError,
        InvalidNormalizedTransactionError,
        InvalidProviderCredentialsError,
        InvalidSyncFrequencyError,
        ConnectionNotActiveError,
        InvalidConnectionStateError,
        DuplicateConnectionError,
        SyncAlreadyInProgressError,
        SyncAlreadyCompletedError,
        InvalidPendingStateError,
        PendingTransactionNotFoundError,
        BankConnectionNotFoundError,
        SyncHistoryNotFoundError,
        ProviderAuthError,
        ProviderError,
    ]

    def test_exactly_16_exception_classes(self) -> None:
        assert len(self.ALL_EXCEPTIONS) == 16

    def test_all_extend_domain_error(self) -> None:
        for cls in self.ALL_EXCEPTIONS:
            assert issubclass(cls, DomainError), f"{cls.__name__} must extend DomainError"

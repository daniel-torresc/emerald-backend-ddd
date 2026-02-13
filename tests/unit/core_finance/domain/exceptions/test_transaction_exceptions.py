from __future__ import annotations

from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    DuplicateExternalIdError,
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
    ParentAccountDeletedError,
    TransactionDeletedError,
    TransactionNotFoundError,
)
from emerald.shared_kernel.domain.exceptions import (
    ConflictError,
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)


class TestDuplicateExternalIdError:
    def test_hierarchy(self) -> None:
        assert issubclass(DuplicateExternalIdError, ConflictError)

    def test_default_code(self) -> None:
        err = DuplicateExternalIdError()
        assert err.code == "DUPLICATE_EXTERNAL_ID"

    def test_default_message(self) -> None:
        err = DuplicateExternalIdError()
        assert err.message == "Duplicate external ID"

    def test_custom_message(self) -> None:
        err = DuplicateExternalIdError("ext-123 already used")
        assert err.message == "ext-123 already used"


class TestTransactionNotFoundError:
    def test_hierarchy(self) -> None:
        assert issubclass(TransactionNotFoundError, NotFoundError)

    def test_default_code(self) -> None:
        err = TransactionNotFoundError()
        assert err.code == "TRANSACTION_NOT_FOUND"

    def test_default_message(self) -> None:
        err = TransactionNotFoundError()
        assert err.message == "Transaction not found"

    def test_custom_message(self) -> None:
        err = TransactionNotFoundError("tx abc not found")
        assert err.message == "tx abc not found"


class TestTransactionDeletedError:
    def test_hierarchy(self) -> None:
        assert issubclass(TransactionDeletedError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = TransactionDeletedError()
        assert err.code == "TRANSACTION_DELETED"

    def test_default_message(self) -> None:
        err = TransactionDeletedError()
        assert err.message == "Transaction is deleted"

    def test_custom_message(self) -> None:
        err = TransactionDeletedError("cannot update deleted tx")
        assert err.message == "cannot update deleted tx"


class TestEmptyDescriptionError:
    def test_hierarchy(self) -> None:
        assert issubclass(EmptyDescriptionError, InvalidValueError)

    def test_default_code(self) -> None:
        err = EmptyDescriptionError()
        assert err.code == "EMPTY_DESCRIPTION"

    def test_default_message(self) -> None:
        err = EmptyDescriptionError()
        assert err.message == "Description cannot be empty"

    def test_custom_message(self) -> None:
        err = EmptyDescriptionError("original_description cannot be empty")
        assert err.message == "original_description cannot be empty"


class TestInvalidMerchantError:
    def test_hierarchy(self) -> None:
        assert issubclass(InvalidMerchantError, InvalidValueError)

    def test_default_code(self) -> None:
        err = InvalidMerchantError()
        assert err.code == "INVALID_MERCHANT"

    def test_default_message(self) -> None:
        err = InvalidMerchantError()
        assert err.message == "Invalid merchant"

    def test_custom_message(self) -> None:
        err = InvalidMerchantError("merchant too long")
        assert err.message == "merchant too long"


class TestInvalidCommentsError:
    def test_hierarchy(self) -> None:
        assert issubclass(InvalidCommentsError, InvalidValueError)

    def test_default_code(self) -> None:
        err = InvalidCommentsError()
        assert err.code == "INVALID_COMMENTS"

    def test_default_message(self) -> None:
        err = InvalidCommentsError()
        assert err.message == "Invalid comments"

    def test_custom_message(self) -> None:
        err = InvalidCommentsError("comments too long")
        assert err.message == "comments too long"


class TestParentAccountDeletedError:
    def test_hierarchy(self) -> None:
        assert issubclass(ParentAccountDeletedError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = ParentAccountDeletedError()
        assert err.code == "PARENT_ACCOUNT_DELETED"

    def test_default_message(self) -> None:
        err = ParentAccountDeletedError()
        assert err.message == "Parent account is deleted"

    def test_custom_message(self) -> None:
        err = ParentAccountDeletedError("account xyz is deleted")
        assert err.message == "account xyz is deleted"

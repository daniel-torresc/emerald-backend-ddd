from __future__ import annotations

from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    AlreadySplitError,
    CannotSplitChildError,
    DuplicateExternalIdError,
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
    MaxSplitsExceededError,
    MinimumSplitsRequiredError,
    NotSplitParentError,
    ParentAccountDeletedError,
    ParentDeletedError,
    SplitAmountMismatchError,
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


# -- Split-related exceptions (Spec 010) --------------------------------------


class TestMinimumSplitsRequiredError:
    def test_hierarchy(self) -> None:
        assert issubclass(MinimumSplitsRequiredError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = MinimumSplitsRequiredError()
        assert err.code == "MINIMUM_SPLITS_REQUIRED"

    def test_default_message(self) -> None:
        err = MinimumSplitsRequiredError()
        assert err.message == "At least 2 splits are required"


class TestMaxSplitsExceededError:
    def test_hierarchy(self) -> None:
        assert issubclass(MaxSplitsExceededError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = MaxSplitsExceededError()
        assert err.code == "MAX_SPLITS_EXCEEDED"

    def test_default_message(self) -> None:
        err = MaxSplitsExceededError()
        assert err.message == "Maximum 50 splits per transaction"


class TestSplitAmountMismatchError:
    def test_hierarchy(self) -> None:
        assert issubclass(SplitAmountMismatchError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = SplitAmountMismatchError()
        assert err.code == "SPLIT_AMOUNT_MISMATCH"

    def test_default_message(self) -> None:
        err = SplitAmountMismatchError()
        assert err.message == "Split amounts do not sum to parent amount"

    def test_with_expected_actual(self) -> None:
        err = SplitAmountMismatchError(expected="85.00 USD", actual="80.00 USD")
        assert "expected 85.00 USD" in err.message
        assert "got 80.00 USD" in err.message


class TestCannotSplitChildError:
    def test_hierarchy(self) -> None:
        assert issubclass(CannotSplitChildError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = CannotSplitChildError()
        assert err.code == "CANNOT_SPLIT_CHILD"

    def test_default_message(self) -> None:
        err = CannotSplitChildError()
        assert err.message == "Cannot split a split child transaction"


class TestAlreadySplitError:
    def test_hierarchy(self) -> None:
        assert issubclass(AlreadySplitError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = AlreadySplitError()
        assert err.code == "ALREADY_SPLIT"

    def test_default_message(self) -> None:
        err = AlreadySplitError()
        assert err.message == "Transaction is already split"


class TestNotSplitParentError:
    def test_hierarchy(self) -> None:
        assert issubclass(NotSplitParentError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = NotSplitParentError()
        assert err.code == "NOT_SPLIT_PARENT"

    def test_default_message(self) -> None:
        err = NotSplitParentError()
        assert err.message == "Transaction is not a split parent"


class TestParentDeletedError:
    def test_hierarchy(self) -> None:
        assert issubclass(ParentDeletedError, InvariantViolationError)

    def test_default_code(self) -> None:
        err = ParentDeletedError()
        assert err.code == "PARENT_DELETED"

    def test_default_message(self) -> None:
        err = ParentDeletedError()
        assert err.message == "Parent transaction is deleted"

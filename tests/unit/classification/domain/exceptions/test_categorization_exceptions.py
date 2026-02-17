from emerald.classification.domain.exceptions.categorization_exceptions import (
    AssignmentNotFoundError,
    TransactionNotActiveError,
)
from emerald.shared_kernel.domain.exceptions import NotFoundError


class TestTransactionNotActiveError:
    def test_default_code(self) -> None:
        err = TransactionNotActiveError()
        assert err.code == "TRANSACTION_NOT_ACTIVE"

    def test_inherits_not_found(self) -> None:
        assert isinstance(TransactionNotActiveError(), NotFoundError)

    def test_custom_message(self) -> None:
        err = TransactionNotActiveError("tx 123 deleted")
        assert str(err) == "tx 123 deleted"


class TestAssignmentNotFoundError:
    def test_default_code(self) -> None:
        err = AssignmentNotFoundError()
        assert err.code == "ASSIGNMENT_NOT_FOUND"

    def test_inherits_not_found(self) -> None:
        assert isinstance(AssignmentNotFoundError(), NotFoundError)

    def test_custom_message(self) -> None:
        err = AssignmentNotFoundError("no assignment for tx+tax")
        assert str(err) == "no assignment for tx+tax"

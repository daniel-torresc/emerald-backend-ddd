from emerald.core_finance.domain.exceptions.bulk_exceptions import (
    BulkLimitExceededError,
    EmptyBulkRequestError,
    EmptyBulkUpdateError,
)
from emerald.shared_kernel.domain.exceptions import (
    InvalidValueError,
    InvariantViolationError,
)


class TestBulkLimitExceededError:
    def test_construction(self) -> None:
        e = BulkLimitExceededError()
        assert e.code == "BULK_LIMIT_EXCEEDED"
        assert "1000" in str(e)

    def test_custom_message(self) -> None:
        e = BulkLimitExceededError("Custom message")
        assert str(e) == "Custom message"

    def test_is_invariant_violation(self) -> None:
        e = BulkLimitExceededError()
        assert isinstance(e, InvariantViolationError)


class TestEmptyBulkRequestError:
    def test_construction(self) -> None:
        e = EmptyBulkRequestError()
        assert e.code == "EMPTY_BULK_REQUEST"
        assert "at least one" in str(e)

    def test_custom_message(self) -> None:
        e = EmptyBulkRequestError("No items")
        assert str(e) == "No items"

    def test_is_invariant_violation(self) -> None:
        e = EmptyBulkRequestError()
        assert isinstance(e, InvariantViolationError)


class TestEmptyBulkUpdateError:
    def test_construction(self) -> None:
        e = EmptyBulkUpdateError()
        assert e.code == "EMPTY_BULK_UPDATE"
        assert "at least one field" in str(e).lower()

    def test_custom_message(self) -> None:
        e = EmptyBulkUpdateError("Nothing to update")
        assert str(e) == "Nothing to update"

    def test_is_invalid_value(self) -> None:
        e = EmptyBulkUpdateError()
        assert isinstance(e, InvalidValueError)

import pytest

from emerald.shared_kernel.domain.exceptions import (
    AlreadyDeletedError,
    AlreadyExistsError,
    AuthorizationError,
    ConflictError,
    CurrencyMismatchError,
    DomainError,
    InvalidValueError,
    InvariantViolationError,
    NotDeletedError,
    NotFoundError,
    ValidationError,
)


class TestExceptionHierarchy:
    """All exception types extend DomainError with correct hierarchy."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ValidationError,
            InvalidValueError,
            InvariantViolationError,
            NotFoundError,
            ConflictError,
            AlreadyExistsError,
            AlreadyDeletedError,
            NotDeletedError,
            AuthorizationError,
            CurrencyMismatchError,
        ],
    )
    def test_all_extend_domain_error(self, exc_cls: type[DomainError]) -> None:
        assert issubclass(exc_cls, DomainError)

    def test_validation_subtypes(self) -> None:
        assert issubclass(InvalidValueError, ValidationError)
        assert issubclass(InvariantViolationError, ValidationError)

    def test_conflict_subtypes(self) -> None:
        assert issubclass(AlreadyExistsError, ConflictError)
        assert issubclass(AlreadyDeletedError, ConflictError)

    def test_not_deleted_is_direct_subclass_of_domain_error(self) -> None:
        assert issubclass(NotDeletedError, DomainError)
        assert not issubclass(NotDeletedError, ConflictError)

    def test_currency_mismatch_is_direct_subclass_of_domain_error(self) -> None:
        assert issubclass(CurrencyMismatchError, DomainError)
        assert not issubclass(CurrencyMismatchError, ValidationError)


class TestExceptionAttributes:
    """Every exception carries code and message."""

    def test_domain_error_has_code_and_message(self) -> None:
        err = DomainError("something went wrong")
        assert err.code == "DOMAIN_ERROR"
        assert err.message == "something went wrong"

    @pytest.mark.parametrize(
        ("exc_cls", "expected_code"),
        [
            (DomainError, "DOMAIN_ERROR"),
            (ValidationError, "VALIDATION_ERROR"),
            (InvalidValueError, "INVALID_VALUE"),
            (InvariantViolationError, "INVARIANT_VIOLATION"),
            (NotFoundError, "NOT_FOUND"),
            (ConflictError, "CONFLICT"),
            (AlreadyExistsError, "ALREADY_EXISTS"),
            (AlreadyDeletedError, "ALREADY_DELETED"),
            (NotDeletedError, "NOT_DELETED"),
            (AuthorizationError, "AUTHORIZATION_ERROR"),
            (CurrencyMismatchError, "CURRENCY_MISMATCH"),
        ],
    )
    def test_default_codes(self, exc_cls: type[DomainError], expected_code: str) -> None:
        err = exc_cls("test message")
        assert err.code == expected_code
        assert err.message == "test message"

    def test_custom_code_overrides_default(self) -> None:
        err = InvalidValueError("bad value", code="CUSTOM_CODE")
        assert err.code == "CUSTOM_CODE"
        assert err.message == "bad value"

    def test_str_representation_includes_message(self) -> None:
        err = DomainError("something broke")
        assert "something broke" in str(err)


class TestExceptionCatchability:
    """Exceptions are catchable by parent type."""

    def test_already_deleted_caught_by_conflict(self) -> None:
        with pytest.raises(ConflictError):
            raise AlreadyDeletedError("already deleted")

    def test_already_exists_caught_by_conflict(self) -> None:
        with pytest.raises(ConflictError):
            raise AlreadyExistsError("already exists")

    def test_invalid_value_caught_by_validation(self) -> None:
        with pytest.raises(ValidationError):
            raise InvalidValueError("invalid")

    def test_invariant_violation_caught_by_validation(self) -> None:
        with pytest.raises(ValidationError):
            raise InvariantViolationError("invariant broken")

    def test_all_caught_by_domain_error(self) -> None:
        with pytest.raises(DomainError):
            raise CurrencyMismatchError("mismatch")

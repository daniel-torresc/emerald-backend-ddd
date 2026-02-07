import pytest

from emerald.iam.domain.exceptions import (
    CannotUnlinkLastProviderError,
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidStateTransitionError,
    InvalidUsernameError,
    PasswordAlreadySetError,
    PasswordReusedError,
    PasswordTooWeakError,
    ProviderAlreadyLinkedError,
    ProviderNotLinkedError,
    UsernameAlreadyExistsError,
)
from emerald.shared_kernel.domain.exceptions import (
    AlreadyExistsError,
    ConflictError,
    DomainError,
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
    ValidationError,
)


class TestIAMExceptionHierarchy:
    """All IAM exceptions extend correct Shared Kernel parents."""

    @pytest.mark.parametrize(
        ("exception_cls", "parent_cls", "code"),
        [
            (InvalidEmailError, InvalidValueError, "INVALID_EMAIL"),
            (InvalidUsernameError, InvalidValueError, "INVALID_USERNAME"),
            (PasswordTooWeakError, InvalidValueError, "PASSWORD_TOO_WEAK"),
            (InvalidStateTransitionError, InvariantViolationError, "INVALID_STATE_TRANSITION"),
            (EmailAlreadyExistsError, AlreadyExistsError, "EMAIL_ALREADY_EXISTS"),
            (UsernameAlreadyExistsError, AlreadyExistsError, "USERNAME_ALREADY_EXISTS"),
            (ProviderAlreadyLinkedError, ConflictError, "PROVIDER_ALREADY_LINKED"),
            (PasswordAlreadySetError, ConflictError, "PASSWORD_ALREADY_SET"),
            (ProviderNotLinkedError, NotFoundError, "PROVIDER_NOT_LINKED"),
            (PasswordReusedError, ValidationError, "PASSWORD_REUSED"),
            (CannotUnlinkLastProviderError, InvariantViolationError, "CANNOT_UNLINK_LAST_PROVIDER"),
        ],
    )
    def test_exception_inherits_parent(self, exception_cls, parent_cls, code):
        exc = exception_cls()
        assert isinstance(exc, parent_cls)
        assert isinstance(exc, DomainError)
        assert exc.code == code

    @pytest.mark.parametrize(
        ("exception_cls", "code"),
        [
            (InvalidEmailError, "INVALID_EMAIL"),
            (InvalidUsernameError, "INVALID_USERNAME"),
            (PasswordTooWeakError, "PASSWORD_TOO_WEAK"),
            (InvalidStateTransitionError, "INVALID_STATE_TRANSITION"),
            (EmailAlreadyExistsError, "EMAIL_ALREADY_EXISTS"),
            (UsernameAlreadyExistsError, "USERNAME_ALREADY_EXISTS"),
            (ProviderAlreadyLinkedError, "PROVIDER_ALREADY_LINKED"),
            (PasswordAlreadySetError, "PASSWORD_ALREADY_SET"),
            (ProviderNotLinkedError, "PROVIDER_NOT_LINKED"),
            (PasswordReusedError, "PASSWORD_REUSED"),
            (CannotUnlinkLastProviderError, "CANNOT_UNLINK_LAST_PROVIDER"),
        ],
    )
    def test_exception_has_code_and_message(self, exception_cls, code):
        exc = exception_cls("custom message")
        assert exc.code == code
        assert exc.message == "custom message"
        assert str(exc) == "custom message"

    def test_catch_by_parent_invalid_value(self):
        with pytest.raises(InvalidValueError):
            raise InvalidEmailError("bad email")

    def test_catch_by_parent_conflict(self):
        with pytest.raises(ConflictError):
            raise ProviderAlreadyLinkedError("already linked")

    def test_catch_by_domain_error(self):
        with pytest.raises(DomainError):
            raise CannotUnlinkLastProviderError("cannot unlink")

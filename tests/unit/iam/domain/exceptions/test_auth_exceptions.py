import pytest

from emerald.iam.domain.exceptions import (
    AccountSuspendedError,
    AuthenticationFailedError,
    EmailNotVerifiedError,
    InvalidTokenError,
    TokenAlreadyRevokedError,
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from emerald.shared_kernel.domain.exceptions import (
    ConflictError,
    DomainError,
    InvalidValueError,
)


class TestAuthExceptionHierarchy:
    @pytest.mark.parametrize(
        ("exception_cls", "parent_cls", "code"),
        [
            (AuthenticationFailedError, DomainError, "AUTHENTICATION_FAILED"),
            (EmailNotVerifiedError, DomainError, "EMAIL_NOT_VERIFIED"),
            (AccountSuspendedError, DomainError, "ACCOUNT_SUSPENDED"),
            (InvalidTokenError, InvalidValueError, "INVALID_TOKEN"),
            (TokenExpiredError, DomainError, "TOKEN_EXPIRED"),
            (TokenAlreadyRevokedError, ConflictError, "TOKEN_ALREADY_REVOKED"),
            (TokenAlreadyUsedError, ConflictError, "TOKEN_ALREADY_USED"),
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
            (AuthenticationFailedError, "AUTHENTICATION_FAILED"),
            (EmailNotVerifiedError, "EMAIL_NOT_VERIFIED"),
            (AccountSuspendedError, "ACCOUNT_SUSPENDED"),
            (InvalidTokenError, "INVALID_TOKEN"),
            (TokenExpiredError, "TOKEN_EXPIRED"),
            (TokenAlreadyRevokedError, "TOKEN_ALREADY_REVOKED"),
            (TokenAlreadyUsedError, "TOKEN_ALREADY_USED"),
        ],
    )
    def test_exception_allows_message_override(self, exception_cls, code):
        exc = exception_cls("custom override message")
        assert exc.code == code
        assert exc.message == "custom override message"
        assert str(exc) == "custom override message"


class TestAuthenticationFailedError:
    def test_default_message_is_vague(self):
        exc = AuthenticationFailedError()
        # The default message should NOT reveal whether the user exists, email is wrong, etc.
        assert "Authentication failed" in exc.message
        assert "email" not in exc.message.lower()
        assert "password" not in exc.message.lower()
        assert "not found" not in exc.message.lower()

    def test_catch_by_domain_error(self):
        with pytest.raises(DomainError):
            raise AuthenticationFailedError()


class TestInvalidTokenError:
    def test_extends_invalid_value_error(self):
        exc = InvalidTokenError()
        assert isinstance(exc, InvalidValueError)

    def test_catch_by_invalid_value_error(self):
        with pytest.raises(InvalidValueError):
            raise InvalidTokenError()


class TestTokenAlreadyRevokedError:
    def test_extends_conflict_error(self):
        exc = TokenAlreadyRevokedError()
        assert isinstance(exc, ConflictError)

    def test_catch_by_conflict_error(self):
        with pytest.raises(ConflictError):
            raise TokenAlreadyRevokedError()


class TestTokenAlreadyUsedError:
    def test_extends_conflict_error(self):
        exc = TokenAlreadyUsedError()
        assert isinstance(exc, ConflictError)

    def test_catch_by_conflict_error(self):
        with pytest.raises(ConflictError):
            raise TokenAlreadyUsedError()

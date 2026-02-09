import pytest

from emerald.iam.domain.exceptions import (
    OAuthCodeExchangeError,
    OAuthStateInvalidError,
    ProviderEmailMismatchError,
    ProviderEmailNotVerifiedError,
    ProviderExternalIdMismatchError,
)
from emerald.shared_kernel.domain.exceptions import ConflictError, DomainError


class TestSocialAuthExceptionHierarchy:
    @pytest.mark.parametrize(
        ("exception_cls", "parent_cls", "code"),
        [
            (ProviderEmailNotVerifiedError, DomainError, "PROVIDER_EMAIL_NOT_VERIFIED"),
            (ProviderEmailMismatchError, DomainError, "PROVIDER_EMAIL_MISMATCH"),
            (ProviderExternalIdMismatchError, ConflictError, "PROVIDER_EXTERNAL_ID_MISMATCH"),
            (OAuthStateInvalidError, DomainError, "OAUTH_STATE_INVALID"),
            (OAuthCodeExchangeError, DomainError, "OAUTH_CODE_EXCHANGE_FAILED"),
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
            (ProviderEmailNotVerifiedError, "PROVIDER_EMAIL_NOT_VERIFIED"),
            (ProviderEmailMismatchError, "PROVIDER_EMAIL_MISMATCH"),
            (ProviderExternalIdMismatchError, "PROVIDER_EXTERNAL_ID_MISMATCH"),
            (OAuthStateInvalidError, "OAUTH_STATE_INVALID"),
            (OAuthCodeExchangeError, "OAUTH_CODE_EXCHANGE_FAILED"),
        ],
    )
    def test_exception_allows_message_override(self, exception_cls, code):
        exc = exception_cls("custom override message")
        assert exc.code == code
        assert exc.message == "custom override message"
        assert str(exc) == "custom override message"


class TestProviderEmailNotVerifiedError:
    def test_default_message(self):
        exc = ProviderEmailNotVerifiedError()
        assert "verified" in exc.message.lower()

    def test_catch_by_domain_error(self):
        with pytest.raises(DomainError):
            raise ProviderEmailNotVerifiedError()


class TestProviderEmailMismatchError:
    def test_default_message(self):
        exc = ProviderEmailMismatchError()
        assert "email" in exc.message.lower()

    def test_catch_by_domain_error(self):
        with pytest.raises(DomainError):
            raise ProviderEmailMismatchError()


class TestProviderExternalIdMismatchError:
    def test_extends_conflict_error(self):
        exc = ProviderExternalIdMismatchError()
        assert isinstance(exc, ConflictError)

    def test_catch_by_conflict_error(self):
        with pytest.raises(ConflictError):
            raise ProviderExternalIdMismatchError()

    def test_default_message(self):
        exc = ProviderExternalIdMismatchError()
        assert "identity" in exc.message.lower() or "linked" in exc.message.lower()


class TestOAuthStateInvalidError:
    def test_default_message(self):
        exc = OAuthStateInvalidError()
        assert "expired" in exc.message.lower() or "session" in exc.message.lower()

    def test_catch_by_domain_error(self):
        with pytest.raises(DomainError):
            raise OAuthStateInvalidError()


class TestOAuthCodeExchangeError:
    def test_default_message(self):
        exc = OAuthCodeExchangeError()
        assert "failed" in exc.message.lower() or "try again" in exc.message.lower()

    def test_catch_by_domain_error(self):
        with pytest.raises(DomainError):
            raise OAuthCodeExchangeError()

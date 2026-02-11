import pytest

from emerald.iam.domain.models.value_objects.auth_provider import ProviderType
from emerald.iam.domain.models.value_objects.oidc_claims import OidcClaims
from emerald.shared_kernel.domain.exceptions import InvalidValueError


class TestOidcClaimsValidConstruction:
    def test_valid_google_provider(self):
        claims = OidcClaims(
            provider_type=ProviderType.GOOGLE,
            external_id="google-12345",
            email="user@gmail.com",
            email_verified=True,
        )
        assert claims.provider_type == ProviderType.GOOGLE
        assert claims.external_id == "google-12345"
        assert claims.email == "user@gmail.com"
        assert claims.email_verified is True
        assert claims.full_name is None

    def test_valid_microsoft_provider(self):
        claims = OidcClaims(
            provider_type=ProviderType.MICROSOFT,
            external_id="ms-abc-def",
            email="user@outlook.com",
            email_verified=True,
        )
        assert claims.provider_type == ProviderType.MICROSOFT
        assert claims.external_id == "ms-abc-def"
        assert claims.email == "user@outlook.com"
        assert claims.email_verified is True

    def test_full_name_none_by_default(self):
        claims = OidcClaims(
            provider_type=ProviderType.GOOGLE,
            external_id="google-12345",
            email="user@gmail.com",
            email_verified=True,
        )
        assert claims.full_name is None

    def test_full_name_string(self):
        claims = OidcClaims(
            provider_type=ProviderType.GOOGLE,
            external_id="google-12345",
            email="user@gmail.com",
            email_verified=True,
            full_name="Jane Doe",
        )
        assert claims.full_name == "Jane Doe"


class TestOidcClaimsProviderTypeValidation:
    def test_password_provider_rejected(self):
        with pytest.raises(InvalidValueError, match="PASSWORD"):
            OidcClaims(
                provider_type=ProviderType.PASSWORD,
                external_id="ext-123",
                email="user@example.com",
                email_verified=True,
            )


class TestOidcClaimsExternalIdValidation:
    def test_empty_external_id_rejected(self):
        with pytest.raises(InvalidValueError, match="external_id"):
            OidcClaims(
                provider_type=ProviderType.GOOGLE,
                external_id="",
                email="user@gmail.com",
                email_verified=True,
            )

    def test_whitespace_only_external_id_rejected(self):
        with pytest.raises(InvalidValueError, match="external_id"):
            OidcClaims(
                provider_type=ProviderType.GOOGLE,
                external_id="   ",
                email="user@gmail.com",
                email_verified=True,
            )


class TestOidcClaimsEmailValidation:
    def test_empty_email_rejected(self):
        with pytest.raises(InvalidValueError, match="email"):
            OidcClaims(
                provider_type=ProviderType.GOOGLE,
                external_id="google-12345",
                email="",
                email_verified=True,
            )


class TestOidcClaimsEmailVerifiedValidation:
    def test_email_verified_false_rejected(self):
        with pytest.raises(InvalidValueError, match="verified"):
            OidcClaims(
                provider_type=ProviderType.GOOGLE,
                external_id="google-12345",
                email="user@gmail.com",
                email_verified=False,
            )


class TestOidcClaimsImmutability:
    def test_frozen(self):
        claims = OidcClaims(
            provider_type=ProviderType.GOOGLE,
            external_id="google-12345",
            email="user@gmail.com",
            email_verified=True,
        )
        with pytest.raises(AttributeError):
            claims.external_id = "other"  # type: ignore[misc]

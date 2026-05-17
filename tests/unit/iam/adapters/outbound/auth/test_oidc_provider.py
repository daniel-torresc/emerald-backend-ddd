from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from emerald.iam.adapters.outbound.auth.oidc_provider import OidcProviderAdapter
from emerald.iam.domain.exceptions import OAuthCodeExchangeError
from emerald.iam.domain.models.value_objects.auth_provider import ProviderType
from emerald.shared_kernel.infrastructure.config.settings import OidcSettings


@pytest.fixture
def rsa_private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def rsa_private_key_pem(rsa_private_key: rsa.RSAPrivateKey) -> bytes:
    return rsa_private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )


@pytest.fixture
def oidc_settings() -> OidcSettings:
    return OidcSettings(
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        google_redirect_uri="http://localhost/callback/google",
        microsoft_client_id="microsoft-client-id",
        microsoft_client_secret="microsoft-client-secret",
        microsoft_redirect_uri="http://localhost/callback/microsoft",
    )


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock()


def _make_id_token(
    private_key_pem: bytes,
    *,
    sub: str = "ext-user-123",
    email: str = "user@example.com",
    email_verified: bool = True,
    name: str = "Test User",
    iss: str = "https://accounts.google.com",
    aud: str = "google-client-id",
    exp_offset: timedelta = timedelta(hours=1),
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "iss": iss,
        "aud": aud,
        "iat": int(now.timestamp()),
        "exp": int((now + exp_offset).timestamp()),
    }
    return pyjwt.encode(payload, private_key_pem, algorithm="RS256")


def _mock_jwk_client(rsa_private_key: rsa.RSAPrivateKey) -> MagicMock:
    """Create a mock PyJWKClient that returns the public key from the given private key."""
    mock_signing_key = MagicMock()
    mock_signing_key.key = rsa_private_key.public_key()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    return mock_client


@pytest.fixture
def adapter(
    oidc_settings: OidcSettings,
    mock_http_client: AsyncMock,
    rsa_private_key: rsa.RSAPrivateKey,
) -> OidcProviderAdapter:
    adapter = OidcProviderAdapter(oidc_settings, mock_http_client)
    # Replace PyJWKClient instances with mocks that use our test key
    mock_client = _mock_jwk_client(rsa_private_key)
    adapter._jwk_clients[ProviderType.GOOGLE] = mock_client
    adapter._jwk_clients[ProviderType.MICROSOFT] = mock_client
    return adapter


class TestGenerateAuthorizationUrl:
    async def test_generate_auth_url_google(self, adapter: OidcProviderAdapter) -> None:
        url = await adapter.generate_authorization_url(
            ProviderType.GOOGLE, "http://localhost/cb", "csrf-state"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "accounts.google.com"
        assert params["client_id"] == ["google-client-id"]
        assert params["redirect_uri"] == ["http://localhost/cb"]
        assert params["response_type"] == ["code"]
        assert params["scope"] == ["openid email profile"]
        assert params["state"] == ["csrf-state"]
        assert "nonce" in params
        assert params["access_type"] == ["offline"]

    async def test_generate_auth_url_microsoft(self, adapter: OidcProviderAdapter) -> None:
        url = await adapter.generate_authorization_url(
            ProviderType.MICROSOFT, "http://localhost/cb", "csrf-state"
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert "login.microsoftonline.com" in parsed.netloc
        assert params["client_id"] == ["microsoft-client-id"]
        assert "access_type" not in params  # Google-only

    async def test_generate_auth_url_unconfigured_provider_raises(
        self, mock_http_client: AsyncMock
    ) -> None:
        settings = OidcSettings()  # No providers configured
        adapter = OidcProviderAdapter(settings, mock_http_client)

        with pytest.raises(OAuthCodeExchangeError):
            await adapter.generate_authorization_url(
                ProviderType.GOOGLE, "http://localhost/cb", "state"
            )

    async def test_generate_auth_url_password_provider_raises(
        self, adapter: OidcProviderAdapter
    ) -> None:
        with pytest.raises(OAuthCodeExchangeError, match="PASSWORD is not a social provider"):
            await adapter.generate_authorization_url(
                ProviderType.PASSWORD, "http://localhost/cb", "state"
            )


class TestExchangeCodeForClaims:
    async def test_exchange_code_success_google(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
        rsa_private_key_pem: bytes,
    ) -> None:
        id_token = _make_id_token(
            rsa_private_key_pem,
            iss="https://accounts.google.com",
            aud="google-client-id",
        )
        response_mock = MagicMock()
        response_mock.json.return_value = {"id_token": id_token, "access_token": "at"}
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        claims = await adapter.exchange_code_for_claims(
            ProviderType.GOOGLE, "auth-code", "http://localhost/cb"
        )

        assert claims.provider_type == ProviderType.GOOGLE
        assert claims.external_id == "ext-user-123"
        assert claims.email == "user@example.com"
        assert claims.email_verified is True
        assert claims.full_name == "Test User"

    async def test_exchange_code_success_microsoft(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
        rsa_private_key_pem: bytes,
    ) -> None:
        id_token = _make_id_token(
            rsa_private_key_pem,
            iss="https://login.microsoftonline.com/tenant-id/v2.0",
            aud="microsoft-client-id",
        )
        response_mock = MagicMock()
        response_mock.json.return_value = {"id_token": id_token}
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        claims = await adapter.exchange_code_for_claims(
            ProviderType.MICROSOFT, "auth-code", "http://localhost/cb"
        )

        assert claims.provider_type == ProviderType.MICROSOFT
        assert claims.external_id == "ext-user-123"
        assert claims.email == "user@example.com"

    async def test_exchange_code_http_error_raises(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
    ) -> None:
        import httpx

        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        with pytest.raises(OAuthCodeExchangeError, match="Token exchange failed"):
            await adapter.exchange_code_for_claims(
                ProviderType.GOOGLE, "code", "http://localhost/cb"
            )

    async def test_exchange_code_no_id_token_raises(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
    ) -> None:
        response_mock = MagicMock()
        response_mock.json.return_value = {"access_token": "at"}  # No id_token
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        with pytest.raises(OAuthCodeExchangeError, match="No id_token"):
            await adapter.exchange_code_for_claims(
                ProviderType.GOOGLE, "code", "http://localhost/cb"
            )

    async def test_exchange_code_invalid_signature_raises(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
    ) -> None:
        # Create a token signed with a DIFFERENT key
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        id_token = _make_id_token(other_pem, aud="google-client-id")

        # But the adapter's JWK client returns the original key — signature mismatch
        response_mock = MagicMock()
        response_mock.json.return_value = {"id_token": id_token}
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        with pytest.raises(OAuthCodeExchangeError):
            await adapter.exchange_code_for_claims(
                ProviderType.GOOGLE, "code", "http://localhost/cb"
            )

    async def test_exchange_code_expired_id_token_raises(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
        rsa_private_key_pem: bytes,
    ) -> None:
        id_token = _make_id_token(
            rsa_private_key_pem,
            aud="google-client-id",
            exp_offset=timedelta(hours=-1),
        )
        response_mock = MagicMock()
        response_mock.json.return_value = {"id_token": id_token}
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        with pytest.raises(OAuthCodeExchangeError):
            await adapter.exchange_code_for_claims(
                ProviderType.GOOGLE, "code", "http://localhost/cb"
            )

    async def test_exchange_code_missing_email_raises(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
        rsa_private_key: rsa.RSAPrivateKey,
        rsa_private_key_pem: bytes,
    ) -> None:
        # Create token without email claim
        now = datetime.now(UTC)
        payload = {
            "sub": "ext-123",
            "iss": "https://accounts.google.com",
            "aud": "google-client-id",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        id_token = pyjwt.encode(payload, rsa_private_key_pem, algorithm="RS256")

        response_mock = MagicMock()
        response_mock.json.return_value = {"id_token": id_token}
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        with pytest.raises(OAuthCodeExchangeError):
            await adapter.exchange_code_for_claims(
                ProviderType.GOOGLE, "code", "http://localhost/cb"
            )

    async def test_exchange_code_unverified_email_raises(
        self,
        adapter: OidcProviderAdapter,
        mock_http_client: AsyncMock,
        rsa_private_key_pem: bytes,
    ) -> None:
        id_token = _make_id_token(
            rsa_private_key_pem,
            email_verified=False,
            aud="google-client-id",
        )
        response_mock = MagicMock()
        response_mock.json.return_value = {"id_token": id_token}
        response_mock.raise_for_status = MagicMock()
        mock_http_client.post.return_value = response_mock

        # OidcClaims.__post_init__ raises InvalidValueError for unverified email
        # which gets caught by the broad except and wrapped in OAuthCodeExchangeError
        with pytest.raises((OAuthCodeExchangeError, Exception)):
            await adapter.exchange_code_for_claims(
                ProviderType.GOOGLE, "code", "http://localhost/cb"
            )

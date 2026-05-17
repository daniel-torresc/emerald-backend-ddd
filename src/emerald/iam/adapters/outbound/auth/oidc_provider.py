import asyncio
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from emerald.iam.domain.exceptions import OAuthCodeExchangeError
from emerald.iam.domain.models.value_objects.auth_provider import ProviderType
from emerald.iam.domain.models.value_objects.oidc_claims import OidcClaims
from emerald.shared_kernel.infrastructure.config.settings import OidcSettings

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUER = "https://accounts.google.com"

_MICROSOFT_AUTH_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_MICROSOFT_TOKEN_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MICROSOFT_JWKS_URI = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_MICROSOFT_ISSUER_PREFIX = "https://login.microsoftonline.com/"


@dataclass(frozen=True)
class _ProviderConfig:
    client_id: str
    client_secret: str
    auth_endpoint: str
    token_endpoint: str
    jwks_uri: str
    issuer: str | None  # None for Microsoft (prefix-validated)


class OidcProviderAdapter:
    """Wraps httpx + PyJWT to implement OidcProviderPort."""

    def __init__(self, settings: OidcSettings, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client
        self._configs: dict[ProviderType, _ProviderConfig] = {}
        self._jwk_clients: dict[ProviderType, PyJWKClient] = {}

        if settings.google_client_id:
            self._configs[ProviderType.GOOGLE] = _ProviderConfig(
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret or "",
                auth_endpoint=_GOOGLE_AUTH_ENDPOINT,
                token_endpoint=_GOOGLE_TOKEN_ENDPOINT,
                jwks_uri=_GOOGLE_JWKS_URI,
                issuer=_GOOGLE_ISSUER,
            )
            self._jwk_clients[ProviderType.GOOGLE] = PyJWKClient(_GOOGLE_JWKS_URI)

        if settings.microsoft_client_id:
            self._configs[ProviderType.MICROSOFT] = _ProviderConfig(
                client_id=settings.microsoft_client_id,
                client_secret=settings.microsoft_client_secret or "",
                auth_endpoint=_MICROSOFT_AUTH_ENDPOINT,
                token_endpoint=_MICROSOFT_TOKEN_ENDPOINT,
                jwks_uri=_MICROSOFT_JWKS_URI,
                issuer=None,
            )
            self._jwk_clients[ProviderType.MICROSOFT] = PyJWKClient(_MICROSOFT_JWKS_URI)

    def _get_config(self, provider_type: ProviderType) -> _ProviderConfig:
        if provider_type == ProviderType.PASSWORD:
            raise OAuthCodeExchangeError("PASSWORD is not a social provider")
        config = self._configs.get(provider_type)
        if config is None:
            raise OAuthCodeExchangeError(f"Provider {provider_type.value} is not configured")
        return config

    async def generate_authorization_url(
        self,
        provider_type: ProviderType,
        redirect_uri: str,
        state: str,
    ) -> str:
        config = self._get_config(provider_type)
        params: dict[str, str] = {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": str(uuid.uuid4()),
        }
        if provider_type == ProviderType.GOOGLE:
            params["access_type"] = "offline"
        return f"{config.auth_endpoint}?{urlencode(params)}"

    async def exchange_code_for_claims(
        self,
        provider_type: ProviderType,
        code: str,
        redirect_uri: str,
    ) -> OidcClaims:
        config = self._get_config(provider_type)
        try:
            response = await self._http_client.post(
                config.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OAuthCodeExchangeError(f"Token exchange failed: {exc}") from exc

        token_data = response.json()
        id_token = token_data.get("id_token")
        if not id_token:
            raise OAuthCodeExchangeError("No id_token in provider response")

        try:
            jwk_client = self._jwk_clients[provider_type]
            signing_key = await asyncio.to_thread(jwk_client.get_signing_key_from_jwt, id_token)

            decode_options: dict[str, object] = {"algorithms": ["RS256"]}
            if config.issuer is not None:
                # Google: strict issuer verification
                decode_options["issuer"] = config.issuer
            else:
                # Microsoft: skip strict issuer, validate prefix manually
                decode_options["options"] = {"verify_iss": False}

            payload = jwt.decode(
                id_token,
                signing_key.key,
                audience=config.client_id,
                **decode_options,  # type: ignore[arg-type]
            )

            # Microsoft: validate issuer prefix
            if config.issuer is None:
                iss = payload.get("iss", "")
                if not iss.startswith(_MICROSOFT_ISSUER_PREFIX):
                    raise OAuthCodeExchangeError(f"Invalid Microsoft issuer: {iss}")

            return OidcClaims(
                provider_type=provider_type,
                external_id=payload["sub"],
                email=payload["email"],
                email_verified=payload.get("email_verified", False),
                full_name=payload.get("name"),
            )
        except OAuthCodeExchangeError:
            raise
        except Exception as exc:
            raise OAuthCodeExchangeError(f"ID token verification failed: {exc}") from exc

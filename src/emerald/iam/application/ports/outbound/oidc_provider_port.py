from typing import Protocol

from emerald.iam.domain.models.value_objects.auth_provider import ProviderType
from emerald.iam.domain.models.value_objects.oidc_claims import OidcClaims


class OidcProviderPort(Protocol):
    """Application port for OIDC provider interactions.

    Infrastructure implements this with provider-specific OAuth clients,
    PKCE management, JWKS verification, and state handling.
    """

    async def generate_authorization_url(
        self,
        provider_type: ProviderType,
        redirect_uri: str,
        state: str,
    ) -> str:
        """Generate the full authorization URL for the given provider."""
        ...

    async def exchange_code_for_claims(
        self,
        provider_type: ProviderType,
        code: str,
        redirect_uri: str,
    ) -> OidcClaims:
        """Exchange an authorization code for verified OIDC claims.

        Raises OAuthCodeExchangeError on failure.
        """
        ...

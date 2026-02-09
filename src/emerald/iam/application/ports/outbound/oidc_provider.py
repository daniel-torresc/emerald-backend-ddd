from typing import Protocol

from emerald.iam.domain.models.auth_provider import ProviderType
from emerald.iam.domain.models.oidc_claims import OidcClaims


class OidcProvider(Protocol):
    """Application port for OIDC provider interactions.

    Infrastructure implements this with provider-specific OAuth clients,
    PKCE management, JWKS verification, and state handling.
    """

    def generate_authorization_url(
        self,
        provider_type: ProviderType,
        redirect_uri: str,
        state: str,
    ) -> str:
        """Generate the full authorization URL for the given provider."""
        ...

    def exchange_code_for_claims(
        self,
        provider_type: ProviderType,
        code: str,
        redirect_uri: str,
    ) -> OidcClaims:
        """Exchange an authorization code for verified OIDC claims.

        Raises OAuthCodeExchangeError on failure.
        """
        ...

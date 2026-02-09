from dataclasses import dataclass

from emerald.iam.domain.models.auth_provider import ProviderType
from emerald.shared_kernel.domain.exceptions import InvalidValueError


@dataclass(frozen=True)
class OidcClaims:
    """Verified claims from an OIDC provider — clean contract between infrastructure and domain."""

    provider_type: ProviderType
    external_id: str
    email: str
    email_verified: bool
    full_name: str | None = None

    def __post_init__(self) -> None:
        if self.provider_type == ProviderType.PASSWORD:
            raise InvalidValueError(
                "OIDC claims cannot use PASSWORD provider type",
                code="INVALID_OIDC_CLAIMS",
            )
        if not self.external_id.strip():
            raise InvalidValueError(
                "external_id must be non-empty",
                code="INVALID_OIDC_CLAIMS",
            )
        if not self.email.strip():
            raise InvalidValueError(
                "email must be non-empty",
                code="INVALID_OIDC_CLAIMS",
            )
        if not self.email_verified:
            raise InvalidValueError(
                "email must be verified by the provider",
                code="INVALID_OIDC_CLAIMS",
            )

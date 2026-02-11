from typing import Protocol

from emerald.iam.domain.models.value_objects.access_token_claims import AccessTokenClaims


class TokenService(Protocol):
    """Domain port for access token signing/verification and refresh token generation.

    Infrastructure implements this with a JWT library and cryptographic random generation.
    """

    def sign_access_token(self, claims: AccessTokenClaims) -> str:
        """Sign claims into a JWT string."""
        ...

    def verify_access_token(self, token: str) -> AccessTokenClaims:
        """Verify JWT and extract claims. Raises InvalidTokenError or TokenExpiredError."""
        ...

    def generate_refresh_token(self) -> tuple[str, str]:
        """Generate (raw_token, token_hash) pair using cryptographically random bytes."""
        ...

    def hash_token(self, raw_token: str) -> str:
        """Hash a raw token value (SHA-256 hex digest)."""
        ...

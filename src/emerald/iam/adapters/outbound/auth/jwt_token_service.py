import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

import jwt

from emerald.iam.domain.exceptions import InvalidTokenError, TokenExpiredError
from emerald.iam.domain.models.value_objects.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.shared_kernel.infrastructure.config.settings import JwtSettings


class JwtTokenService:
    """Wraps PyJWT to implement TokenPort."""

    def __init__(self, settings: JwtSettings) -> None:
        self._secret_key = settings.secret_key
        self._algorithm = settings.algorithm
        self._issuer = settings.issuer

    async def sign_access_token(self, claims: AccessTokenClaims) -> str:
        payload: dict[str, object] = {
            "sub": str(claims.sub),
            "email": claims.email,
            "username": claims.username,
            "system_role": claims.system_role.value,
            "iss": self._issuer,
            "iat": claims.iat,
            "exp": claims.exp,
            "jti": str(claims.jti),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    async def verify_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={"require": ["sub", "email", "system_role", "exp", "iat", "iss", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError(str(exc)) from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError(str(exc)) from exc

        try:
            return AccessTokenClaims(
                sub=UUID(payload["sub"]),
                email=payload["email"],
                username=payload.get("username"),
                system_role=SystemRole(payload["system_role"]),
                iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
                exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
                jti=UUID(payload["jti"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidTokenError(f"Malformed token claims: {exc}") from exc

    async def generate_refresh_token(self) -> tuple[str, str]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return raw_token, token_hash

    async def hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

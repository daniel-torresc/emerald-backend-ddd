import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from emerald.iam.domain.models.system_role import SystemRole
from emerald.shared_kernel import InvalidValueError


@dataclass(frozen=True)
class AccessTokenClaims:
    """Decoded claims from a valid access token. Internal to IAM — never sent downstream."""

    sub: uuid.UUID
    email: str
    system_role: SystemRole
    iat: datetime
    exp: datetime
    jti: uuid.UUID
    username: str | None = None

    def __post_init__(self) -> None:
        if self.iat.tzinfo is None:
            raise InvalidValueError("iat must be timezone-aware UTC", code="INVALID_TOKEN_CLAIMS")
        if self.exp.tzinfo is None:
            raise InvalidValueError("exp must be timezone-aware UTC", code="INVALID_TOKEN_CLAIMS")
        if self.iat.tzinfo != UTC and self.iat.utcoffset() != UTC.utcoffset(None):
            raise InvalidValueError("iat must be UTC", code="INVALID_TOKEN_CLAIMS")
        if self.exp.tzinfo != UTC and self.exp.utcoffset() != UTC.utcoffset(None):
            raise InvalidValueError("exp must be UTC", code="INVALID_TOKEN_CLAIMS")
        if self.exp <= self.iat:
            raise InvalidValueError("exp must be after iat", code="INVALID_TOKEN_CLAIMS")

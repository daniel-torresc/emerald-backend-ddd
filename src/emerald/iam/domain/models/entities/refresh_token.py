import uuid
from datetime import UTC, datetime

from emerald.iam.domain.models.value_objects.portal_context import PortalContext
from emerald.shared_kernel.domain.models.base.entity import Entity


class RefreshToken(Entity):
    """Server-side refresh token for obtaining new access tokens. Stored hashed."""

    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        family_id: uuid.UUID,
        portal_context: PortalContext,
        expires_at: datetime,
        created_at: datetime | None = None,
        revoked_at: datetime | None = None,
        id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(id=id)
        self.user_id = user_id
        self.token_hash = token_hash
        self.family_id = family_id
        self.portal_context = portal_context
        self.expires_at = expires_at
        self.created_at = created_at if created_at is not None else datetime.now(UTC)
        self.revoked_at = revoked_at

    def revoke(self) -> None:
        """Revoke this token. Irreversible."""
        from emerald.iam.domain.exceptions import TokenAlreadyRevokedError

        if self.revoked_at is not None:
            raise TokenAlreadyRevokedError()
        self.revoked_at = datetime.now(UTC)

    def is_active(self) -> bool:
        """Return True if this token is neither revoked nor expired."""
        return not self.is_revoked() and not self.is_expired()

    def is_expired(self) -> bool:
        """Return True if the token has passed its expiration time."""
        return datetime.now(UTC) >= self.expires_at

    def is_revoked(self) -> bool:
        """Return True if the token has been revoked."""
        return self.revoked_at is not None

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from emerald.iam.domain.constants import PASSWORD_RESET_TOKEN_TTL
from emerald.shared_kernel.domain.models.base.entity import Entity


class PasswordResetToken(Entity):
    """Short-lived, single-use token for password reset. Stored hashed.

    Design note: intentionally does NOT use TimestampedMixin. Password reset tokens
    are lightweight entities with a create-then-use-or-expire lifecycle — they do not
    need ``updated_at`` tracking.
    """

    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime | None = None,
        created_at: datetime | None = None,
        used_at: datetime | None = None,
        id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(id=id)
        now = datetime.now(UTC)
        self.user_id = user_id
        self.token_hash = token_hash
        self.created_at = created_at if created_at is not None else now
        self.expires_at = (
            expires_at if expires_at is not None else self.created_at + PASSWORD_RESET_TOKEN_TTL
        )
        self.used_at = used_at

    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime | None = None,
    ) -> PasswordResetToken:
        """Create a new PasswordResetToken with auto-generated id and created_at."""
        return cls(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )

    def mark_used(self) -> None:
        """Mark this token as consumed. Single-use — irreversible."""
        from emerald.iam.domain.exceptions import TokenAlreadyUsedError

        if self.used_at is not None:
            raise TokenAlreadyUsedError()
        self.used_at = datetime.now(UTC)

    def is_valid(self) -> bool:
        """Return True if this token is neither used nor expired."""
        return not self.is_used() and not self.is_expired()

    def is_expired(self) -> bool:
        """Return True if the token has passed its expiration time."""
        return datetime.now(UTC) >= self.expires_at

    def is_used(self) -> bool:
        """Return True if the token has been consumed."""
        return self.used_at is not None

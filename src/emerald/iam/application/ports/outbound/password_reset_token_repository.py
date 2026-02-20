from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from emerald.iam.domain.models.entities.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository(Protocol):
    """Domain port for password reset token persistence."""

    async def add(self, token: PasswordResetToken) -> None:
        """Persist a new reset token."""
        ...

    async def find_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Find token by its hash. Returns None when not found."""
        ...

    async def invalidate_existing_for_user(self, user_id: uuid.UUID) -> None:
        """Invalidate all existing reset tokens for a user."""
        ...

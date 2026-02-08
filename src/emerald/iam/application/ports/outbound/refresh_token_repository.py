from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from emerald.iam.domain.models.refresh_token import RefreshToken


class RefreshTokenRepository(Protocol):
    """Domain port for refresh token persistence."""

    def add(self, token: RefreshToken) -> None:
        """Persist a new refresh token."""
        ...

    def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Find token by its hash. Returns None when not found."""
        ...

    def find_active_families_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """List active (non-expired, non-revoked) family IDs for a user."""
        ...

    def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revoke all tokens in a family."""
        ...

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Revoke all tokens for a user."""
        ...

    def count_active_families(self, user_id: uuid.UUID) -> int:
        """Count active token families for session limit check."""
        ...

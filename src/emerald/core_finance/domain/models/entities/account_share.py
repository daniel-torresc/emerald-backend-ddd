from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from emerald.core_finance.domain.exceptions.sharing_exceptions import ShareAlreadyRevokedError
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.shared_kernel.domain.models.base.entity import Entity


class AccountShare(Entity):
    """Child entity representing a user's access grant to an account.

    Managed inside the Account aggregate — not an aggregate root.
    Uses explicit fields rather than mixins for revocation tracking.

    Design note: intentionally lacks a ``create()`` factory method because it is a
    child entity created exclusively by its parent aggregate (``Account.share_with()``).
    """

    def __init__(
        self,
        *,
        account_id: uuid.UUID,
        user_id: uuid.UUID,
        permission_level: PermissionLevel,
        granted_by: uuid.UUID,
        granted_at: datetime | None = None,
        updated_at: datetime | None = None,
        revoked_at: datetime | None = None,
        revoked_by: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.account_id = account_id
        self.user_id = user_id
        self.permission_level = permission_level
        self.granted_by = granted_by
        now = datetime.now(UTC)
        self.granted_at = granted_at if granted_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self.granted_at
        self.revoked_at = revoked_at
        self.revoked_by = revoked_by

    def is_active(self) -> bool:
        """Return True if this share has not been revoked."""
        return self.revoked_at is None

    def is_revoked(self) -> bool:
        """Return True if this share has been revoked."""
        return self.revoked_at is not None

    def revoke(self, revoked_by: uuid.UUID) -> None:
        """Revoke this share."""
        if self.is_revoked():
            raise ShareAlreadyRevokedError()
        self.revoked_at = datetime.now(UTC)
        self.revoked_by = revoked_by

    def update_permission(self, new_level: PermissionLevel) -> None:
        """Update the permission level."""
        self.permission_level = new_level
        self.updated_at = datetime.now(UTC)

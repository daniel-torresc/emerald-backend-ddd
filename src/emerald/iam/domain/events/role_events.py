import uuid
from dataclasses import dataclass

from emerald.iam.domain.events.base import UserEvent


@dataclass(frozen=True)
class UserPromotedToAdmin(UserEvent):
    """Emitted when a user is promoted from USER to ADMIN."""

    permissions: frozenset[str]
    promoted_by_id: uuid.UUID


@dataclass(frozen=True)
class UserDemotedToUser(UserEvent):
    """Emitted when an admin is demoted back to USER."""

    demoted_by_id: uuid.UUID


@dataclass(frozen=True)
class AdminPermissionGranted(UserEvent):
    """Emitted when an admin permission is granted."""

    permission: str
    granted_by_id: uuid.UUID


@dataclass(frozen=True)
class AdminPermissionRevoked(UserEvent):
    """Emitted when an admin permission is revoked."""

    permission: str
    revoked_by_id: uuid.UUID


@dataclass(frozen=True)
class SuperadminProvisioned(UserEvent):
    """Emitted when the SUPERADMIN account is provisioned."""

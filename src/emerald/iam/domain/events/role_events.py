import uuid
from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserPromotedToAdmin(DomainEvent):
    """Emitted when a user is promoted from USER to ADMIN."""

    permissions: frozenset[str] = frozenset()
    promoted_by_id: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserDemotedToUser(DomainEvent):
    """Emitted when an admin is demoted back to USER."""

    demoted_by_id: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class AdminPermissionGranted(DomainEvent):
    """Emitted when an admin permission is granted."""

    permission: str = ""
    granted_by_id: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class AdminPermissionRevoked(DomainEvent):
    """Emitted when an admin permission is revoked."""

    permission: str = ""
    revoked_by_id: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class SuperadminProvisioned(DomainEvent):
    """Emitted when the SUPERADMIN account is provisioned."""

    aggregate_type: ClassVar[str] = "User"

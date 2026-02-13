import uuid
from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class AccountShared(DomainEvent):
    """Emitted when an account is shared with a user."""

    user_id: uuid.UUID = uuid.UUID(int=0)
    permission_level: str = ""
    granted_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountShareUpdated(DomainEvent):
    """Emitted when a share's permission level is changed."""

    user_id: uuid.UUID = uuid.UUID(int=0)
    old_permission: str = ""
    new_permission: str = ""
    updated_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountShareRevoked(DomainEvent):
    """Emitted when an owner revokes a share."""

    user_id: uuid.UUID = uuid.UUID(int=0)
    revoked_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountShareLeft(DomainEvent):
    """Emitted when a non-owner leaves an account."""

    user_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountOwnershipTransferred(DomainEvent):
    """Emitted when ownership is transferred to another user."""

    old_owner_id: uuid.UUID = uuid.UUID(int=0)
    new_owner_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"

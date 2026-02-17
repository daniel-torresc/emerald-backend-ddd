import uuid
from dataclasses import dataclass

from emerald.core_finance.domain.events.base import AccountEvent


@dataclass(frozen=True)
class AccountShared(AccountEvent):
    """Emitted when an account is shared with a user."""

    user_id: uuid.UUID
    permission_level: str
    granted_by: uuid.UUID


@dataclass(frozen=True)
class AccountShareUpdated(AccountEvent):
    """Emitted when a share's permission level is changed."""

    user_id: uuid.UUID
    old_permission: str
    new_permission: str
    updated_by: uuid.UUID


@dataclass(frozen=True)
class AccountShareRevoked(AccountEvent):
    """Emitted when an owner revokes a share."""

    user_id: uuid.UUID
    revoked_by: uuid.UUID


@dataclass(frozen=True)
class AccountShareLeft(AccountEvent):
    """Emitted when a non-owner leaves an account."""

    user_id: uuid.UUID


@dataclass(frozen=True)
class AccountOwnershipTransferred(AccountEvent):
    """Emitted when ownership is transferred to another user."""

    old_owner_id: uuid.UUID
    new_owner_id: uuid.UUID

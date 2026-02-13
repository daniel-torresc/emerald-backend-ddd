import uuid
from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class ShareAccountWith(Command):
    """Grant share access to a user on an account."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    target_user_id: uuid.UUID = uuid.UUID(int=0)
    permission_level: str = ""


@dataclass(frozen=True)
class UpdateSharePermission(Command):
    """Change a share's permission level."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    target_user_id: uuid.UUID = uuid.UUID(int=0)
    new_permission_level: str = ""


@dataclass(frozen=True)
class RevokeAccountShare(Command):
    """Owner revokes a share."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    target_user_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class LeaveAccountShare(Command):
    """Non-owner removes own share."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class TransferAccountOwnership(Command):
    """Transfer OWNER to another user."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    new_owner_id: uuid.UUID = uuid.UUID(int=0)

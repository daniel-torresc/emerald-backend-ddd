import uuid

from emerald.core_finance.application.dtos.commands.sharing_commands import (
    LeaveAccountShare,
    RevokeAccountShare,
    ShareAccountWith,
    TransferAccountOwnership,
    UpdateSharePermission,
)
from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.entities.account_share import AccountShare
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel


class AccountSharingService:
    """Application service orchestrating account sharing operations."""

    def __init__(self, uow: AbstractCoreFinanceUnitOfWork) -> None:
        self._uow = uow

    def share_account(self, cmd: ShareAccountWith) -> AccountShare:
        """Grant share access to a user."""
        account = self._load_account(cmd.account_id)
        permission = PermissionLevel[cmd.permission_level]
        share = account.share_with(
            user_id=cmd.target_user_id,
            permission=permission,
            granted_by=cmd.requesting_user_id,
        )
        self._uow.commit()
        return share

    def update_share_permission(self, cmd: UpdateSharePermission) -> None:
        """Update a share's permission level."""
        account = self._load_account(cmd.account_id)
        permission = PermissionLevel[cmd.new_permission_level]
        account.update_share_permission(
            user_id=cmd.target_user_id,
            new_permission=permission,
            updated_by=cmd.requesting_user_id,
        )
        self._uow.commit()

    def revoke_share(self, cmd: RevokeAccountShare) -> None:
        """Owner revokes a share."""
        account = self._load_account(cmd.account_id)
        account.revoke_share(
            user_id=cmd.target_user_id,
            revoked_by=cmd.requesting_user_id,
        )
        self._uow.commit()

    def leave_share(self, cmd: LeaveAccountShare) -> None:
        """Non-owner removes own share."""
        account = self._load_account(cmd.account_id)
        account.leave_share(user_id=cmd.requesting_user_id)
        self._uow.commit()

    def transfer_ownership(self, cmd: TransferAccountOwnership) -> None:
        """Transfer ownership to another shared user."""
        account = self._load_account(cmd.account_id)
        account.transfer_ownership(
            new_owner_id=cmd.new_owner_id,
            current_owner_id=cmd.requesting_user_id,
        )
        self._uow.commit()

    def _load_account(self, account_id: uuid.UUID) -> Account:
        """Load an account or raise AccountNotFoundError."""
        account = self._uow.accounts.find_by_id(account_id)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

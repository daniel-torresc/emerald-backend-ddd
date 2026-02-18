import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import CreateAccount
from emerald.core_finance.application.dtos.commands.sharing_commands import (
    LeaveAccountShare,
    RevokeAccountShare,
    ShareAccountWith,
    TransferAccountOwnership,
    UpdateSharePermission,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.application.services.account_sharing import AccountSharingService
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.core_finance.fakes import FakeCoreFinanceUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_services() -> tuple[
    AccountSharingService, AccountManagementService, FakeCoreFinanceUnitOfWork
]:
    uow = FakeCoreFinanceUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    mgmt_service = AccountManagementService(uow=uow, retention_policy_service=retention_service)
    sharing_service = AccountSharingService(uow=uow)
    return sharing_service, mgmt_service, uow


def _make_create_cmd(**overrides: Any) -> CreateAccount:
    defaults: dict[str, Any] = {
        "owner_user_id": uuid.uuid4(),
        "owner_display_name": "Test User",
        "account_name": "My Account",
        "currency_code": "USD",
        "opening_balance": Decimal("0"),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return CreateAccount(**defaults)


class TestShareAccount:
    async def test_shares_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = await mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()

        share = await sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )
        assert share.user_id == target
        assert share.permission_level == PermissionLevel.EDITOR

    async def test_commits_uow(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = await mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        uow.committed = False

        await sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=uuid.uuid4(),
                permission_level="VIEWER",
            )
        )
        assert uow.committed

    async def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            await sharing.share_account(
                ShareAccountWith(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    target_user_id=uuid.uuid4(),
                    permission_level="VIEWER",
                )
            )


class TestUpdateSharePermission:
    async def test_updates_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = await mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        await sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="VIEWER",
            )
        )

        await sharing.update_share_permission(
            UpdateSharePermission(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                new_permission_level="EDITOR",
            )
        )
        assert account.get_permission_level(target) == PermissionLevel.EDITOR

    async def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            await sharing.update_share_permission(
                UpdateSharePermission(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    target_user_id=uuid.uuid4(),
                    new_permission_level="EDITOR",
                )
            )


class TestRevokeShare:
    async def test_revokes_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = await mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        await sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )

        await sharing.revoke_share(
            RevokeAccountShare(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
            )
        )
        assert account.get_share_for_user(target) is None

    async def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            await sharing.revoke_share(
                RevokeAccountShare(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    target_user_id=uuid.uuid4(),
                )
            )


class TestLeaveShare:
    async def test_leaves_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = await mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        await sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )

        await sharing.leave_share(
            LeaveAccountShare(
                account_id=account.id,
                requesting_user_id=target,
            )
        )
        assert account.get_share_for_user(target) is None

    async def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            await sharing.leave_share(
                LeaveAccountShare(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                )
            )


class TestTransferOwnership:
    async def test_transfers_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = await mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        await sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )

        await sharing.transfer_ownership(
            TransferAccountOwnership(
                account_id=account.id,
                requesting_user_id=owner_id,
                new_owner_id=target,
            )
        )
        assert account.is_owner(target)
        assert not account.is_owner(owner_id)

    async def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            await sharing.transfer_ownership(
                TransferAccountOwnership(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    new_owner_id=uuid.uuid4(),
                )
            )

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
    def test_shares_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()

        share = sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )
        assert share.user_id == target
        assert share.permission_level == PermissionLevel.EDITOR

    def test_commits_uow(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        uow.committed = False

        sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=uuid.uuid4(),
                permission_level="VIEWER",
            )
        )
        assert uow.committed

    def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            sharing.share_account(
                ShareAccountWith(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    target_user_id=uuid.uuid4(),
                    permission_level="VIEWER",
                )
            )


class TestUpdateSharePermission:
    def test_updates_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="VIEWER",
            )
        )

        sharing.update_share_permission(
            UpdateSharePermission(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                new_permission_level="EDITOR",
            )
        )
        assert account.get_permission_level(target) == PermissionLevel.EDITOR

    def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            sharing.update_share_permission(
                UpdateSharePermission(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    target_user_id=uuid.uuid4(),
                    new_permission_level="EDITOR",
                )
            )


class TestRevokeShare:
    def test_revokes_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )

        sharing.revoke_share(
            RevokeAccountShare(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
            )
        )
        assert account.get_share_for_user(target) is None

    def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            sharing.revoke_share(
                RevokeAccountShare(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    target_user_id=uuid.uuid4(),
                )
            )


class TestLeaveShare:
    def test_leaves_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )

        sharing.leave_share(
            LeaveAccountShare(
                account_id=account.id,
                requesting_user_id=target,
            )
        )
        assert account.get_share_for_user(target) is None

    def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            sharing.leave_share(
                LeaveAccountShare(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                )
            )


class TestTransferOwnership:
    def test_transfers_successfully(self) -> None:
        sharing, mgmt, uow = _make_services()
        owner_id = uuid.uuid4()
        account = mgmt.create_account(_make_create_cmd(owner_user_id=owner_id))
        target = uuid.uuid4()
        sharing.share_account(
            ShareAccountWith(
                account_id=account.id,
                requesting_user_id=owner_id,
                target_user_id=target,
                permission_level="EDITOR",
            )
        )

        sharing.transfer_ownership(
            TransferAccountOwnership(
                account_id=account.id,
                requesting_user_id=owner_id,
                new_owner_id=target,
            )
        )
        assert account.is_owner(target)
        assert not account.is_owner(owner_id)

    def test_account_not_found(self) -> None:
        sharing, mgmt, uow = _make_services()
        with pytest.raises(AccountNotFoundError):
            sharing.transfer_ownership(
                TransferAccountOwnership(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    new_owner_id=uuid.uuid4(),
                )
            )

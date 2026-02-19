import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import (
    CreateAccount,
    SoftDeleteAccount,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.domain.exceptions import (
    AccountNotFoundError,
    InsufficientPermissionError,
)
from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.core_finance.fakes import FakeCoreFinanceUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_service() -> tuple[AccountManagementService, FakeCoreFinanceUnitOfWork]:
    uow = FakeCoreFinanceUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    service = AccountManagementService(uow=uow, retention_policy_service=retention_service)
    return service, uow


def _make_create_cmd(**overrides: Any) -> CreateAccount:
    defaults: dict[str, Any] = {
        "owner_user_id": uuid.uuid4(),
        "owner_display_name": "Test User",
        "account_name": "My Checking",
        "currency_code": "USD",
        "opening_balance": Decimal("1000.00"),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return CreateAccount(**defaults)


class TestSoftDeleteAccount:
    async def test_soft_deletes_account(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))
        uow.committed = False

        await service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )
        assert account.is_deleted()
        assert uow.committed

    async def test_sets_deletion_reason(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))

        await service.soft_delete_account(
            SoftDeleteAccount(
                account_id=account.id,
                requesting_user_id=uid,
                reason="Closed",
            )
        )
        assert account.deletion_reason == "Closed"

    async def test_hard_delete_scheduled(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))

        await service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )
        assert account.hard_delete_scheduled_at is not None

    async def test_raises_not_found(self) -> None:
        service, uow = _make_service()
        with pytest.raises(AccountNotFoundError):
            await service.soft_delete_account(
                SoftDeleteAccount(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                )
            )

    async def test_raises_insufficient_permission(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(InsufficientPermissionError):
            await service.soft_delete_account(
                SoftDeleteAccount(
                    account_id=account.id,
                    requesting_user_id=uuid.uuid4(),
                )
            )

    async def test_double_delete_raises(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))
        await service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )

        with pytest.raises(AlreadyDeletedError):
            await service.soft_delete_account(
                SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
            )

    async def test_soft_deleted_account_not_found_by_default(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))
        await service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )
        assert await uow.accounts.find_by_id(account.id) is None

    async def test_soft_deleted_account_found_with_include_deleted(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = await service.create_account(_make_create_cmd(owner_user_id=uid))
        await service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )
        found = await uow.accounts.find_by_id(account.id, include_deleted=True)
        assert found is not None

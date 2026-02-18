import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import CreateAccount
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.domain.exceptions import AccountNameAlreadyExistsError
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
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


class TestCreateAccount:
    async def test_creates_account(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd()
        account = await service.create_account(cmd)
        assert account.account_name == AccountName("My Checking")
        assert account.currency == Currency.USD
        assert account.opening_balance.amount == Decimal("1000.00")

    async def test_sets_owner(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        cmd = _make_create_cmd(owner_user_id=uid)
        account = await service.create_account(cmd)
        assert account.created_by == uid

    async def test_saves_to_repository(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd()
        account = await service.create_account(cmd)
        assert uow.accounts.find_by_id(account.id) is not None

    async def test_commits_uow(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd()
        await service.create_account(cmd)
        assert uow.committed

    async def test_with_iban(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd(iban="GB29NWBK60161331926819")
        account = await service.create_account(cmd)
        assert account.iban is not None
        assert account.iban.value == "GB29NWBK60161331926819"

    async def test_with_notes(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd(notes="My account notes")
        account = await service.create_account(cmd)
        assert account.notes == "My account notes"

    async def test_without_iban(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd(iban=None)
        account = await service.create_account(cmd)
        assert account.iban is None


class TestCreateAccountUniqueness:
    async def test_rejects_duplicate_name_for_same_user(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        cmd1 = _make_create_cmd(owner_user_id=uid, account_name="Checking")
        await service.create_account(cmd1)
        cmd2 = _make_create_cmd(owner_user_id=uid, account_name="Checking")
        with pytest.raises(AccountNameAlreadyExistsError):
            await service.create_account(cmd2)

    async def test_rejects_duplicate_name_case_insensitive(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        cmd1 = _make_create_cmd(owner_user_id=uid, account_name="Checking")
        await service.create_account(cmd1)
        cmd2 = _make_create_cmd(owner_user_id=uid, account_name="CHECKING")
        with pytest.raises(AccountNameAlreadyExistsError):
            await service.create_account(cmd2)

    async def test_allows_same_name_for_different_users(self) -> None:
        service, uow = _make_service()
        cmd1 = _make_create_cmd(owner_user_id=uuid.uuid4(), account_name="Checking")
        await service.create_account(cmd1)
        cmd2 = _make_create_cmd(owner_user_id=uuid.uuid4(), account_name="Checking")
        account = await service.create_account(cmd2)
        assert account is not None

    async def test_allows_reuse_of_soft_deleted_name(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        cmd1 = _make_create_cmd(owner_user_id=uid, account_name="Checking")
        account = await service.create_account(cmd1)
        # Soft-delete it
        from emerald.core_finance.application.dtos.commands.account_commands import (
            SoftDeleteAccount,
        )

        await service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )
        # Re-create with same name
        cmd2 = _make_create_cmd(owner_user_id=uid, account_name="Checking")
        new_account = await service.create_account(cmd2)
        assert new_account is not None


class TestCreateAccountValidation:
    async def test_rejects_invalid_currency_code(self) -> None:
        service, uow = _make_service()
        with pytest.raises(KeyError):
            cmd = _make_create_cmd(currency_code="INVALID")
            await service.create_account(cmd)

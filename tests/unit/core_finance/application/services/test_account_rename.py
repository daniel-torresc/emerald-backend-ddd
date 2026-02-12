import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import (
    CreateAccount,
    RenameAccount,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.domain.exceptions import (
    AccountNameAlreadyExistsError,
    AccountNotFoundError,
    NotAccountOwnerError,
)
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
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


class TestRenameAccount:
    def test_renames_successfully(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        uow.committed = False

        service.rename_account(
            RenameAccount(account_id=account.id, requesting_user_id=uid, new_name="Savings")
        )
        assert account.account_name == AccountName("Savings")
        assert uow.committed

    def test_raises_not_found(self) -> None:
        service, uow = _make_service()
        with pytest.raises(AccountNotFoundError):
            service.rename_account(
                RenameAccount(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    new_name="Savings",
                )
            )

    def test_raises_not_owner(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(NotAccountOwnerError):
            service.rename_account(
                RenameAccount(
                    account_id=account.id,
                    requesting_user_id=uuid.uuid4(),
                    new_name="Savings",
                )
            )

    def test_rejects_duplicate_name(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        service.create_account(_make_create_cmd(owner_user_id=uid, account_name="Savings"))
        account = service.create_account(
            _make_create_cmd(owner_user_id=uid, account_name="Checking")
        )

        with pytest.raises(AccountNameAlreadyExistsError):
            service.rename_account(
                RenameAccount(
                    account_id=account.id,
                    requesting_user_id=uid,
                    new_name="Savings",
                )
            )

    def test_rejects_duplicate_name_case_insensitive(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        service.create_account(_make_create_cmd(owner_user_id=uid, account_name="Savings"))
        account = service.create_account(
            _make_create_cmd(owner_user_id=uid, account_name="Checking")
        )

        with pytest.raises(AccountNameAlreadyExistsError):
            service.rename_account(
                RenameAccount(
                    account_id=account.id,
                    requesting_user_id=uid,
                    new_name="SAVINGS",
                )
            )

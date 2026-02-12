import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import (
    CreateAccount,
    RecoverAccount,
    SoftDeleteAccount,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.domain.exceptions import (
    AccountNotFoundError,
    NotAccountOwnerError,
)
from emerald.shared_kernel.domain.exceptions import NotDeletedError
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


class TestRecoverAccount:
    def test_recovers_successfully(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )
        uow.committed = False

        service.recover_account(RecoverAccount(account_id=account.id, requesting_user_id=uid))
        assert account.is_active()
        assert account.deleted_at is None
        assert account.deleted_by is None
        assert account.deletion_reason is None
        assert account.hard_delete_scheduled_at is None
        assert uow.committed

    def test_raises_not_found_for_nonexistent(self) -> None:
        service, uow = _make_service()
        with pytest.raises(AccountNotFoundError):
            service.recover_account(
                RecoverAccount(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                )
            )

    def test_raises_not_owner(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )

        with pytest.raises(NotAccountOwnerError):
            service.recover_account(
                RecoverAccount(
                    account_id=account.id,
                    requesting_user_id=uuid.uuid4(),
                )
            )

    def test_raises_not_deleted(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(NotDeletedError):
            service.recover_account(RecoverAccount(account_id=account.id, requesting_user_id=uid))

    def test_loads_with_include_deleted(self) -> None:
        """The service must use include_deleted=True to find soft-deleted accounts."""
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        service.soft_delete_account(
            SoftDeleteAccount(account_id=account.id, requesting_user_id=uid)
        )

        # If include_deleted were not used, this would raise AccountNotFoundError
        service.recover_account(RecoverAccount(account_id=account.id, requesting_user_id=uid))
        assert account.is_active()

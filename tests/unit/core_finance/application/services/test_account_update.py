import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import (
    CreateAccount,
    UpdateAccountNotes,
    UpdateAccountType,
    UpdateFinancialInstitution,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.domain.exceptions import (
    AccountNotFoundError,
    InvalidAccountNotesError,
    NotAccountOwnerError,
)
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


class TestUpdateAccountType:
    def test_updates_successfully(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        new_type_id = uuid.uuid4()
        uow.committed = False

        service.update_account_type(
            UpdateAccountType(
                account_id=account.id,
                requesting_user_id=uid,
                account_type_id=new_type_id,
            )
        )
        assert account.account_type_id == new_type_id
        assert uow.committed

    def test_raises_not_found(self) -> None:
        service, uow = _make_service()
        with pytest.raises(AccountNotFoundError):
            service.update_account_type(
                UpdateAccountType(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    account_type_id=uuid.uuid4(),
                )
            )

    def test_raises_not_owner(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(NotAccountOwnerError):
            service.update_account_type(
                UpdateAccountType(
                    account_id=account.id,
                    requesting_user_id=uuid.uuid4(),
                    account_type_id=uuid.uuid4(),
                )
            )


class TestUpdateFinancialInstitution:
    def test_updates_successfully(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        new_inst_id = uuid.uuid4()
        uow.committed = False

        service.update_financial_institution(
            UpdateFinancialInstitution(
                account_id=account.id,
                requesting_user_id=uid,
                financial_institution_id=new_inst_id,
            )
        )
        assert account.financial_institution_id == new_inst_id
        assert uow.committed

    def test_raises_not_found(self) -> None:
        service, uow = _make_service()
        with pytest.raises(AccountNotFoundError):
            service.update_financial_institution(
                UpdateFinancialInstitution(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    financial_institution_id=uuid.uuid4(),
                )
            )

    def test_raises_not_owner(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(NotAccountOwnerError):
            service.update_financial_institution(
                UpdateFinancialInstitution(
                    account_id=account.id,
                    requesting_user_id=uuid.uuid4(),
                    financial_institution_id=uuid.uuid4(),
                )
            )


class TestUpdateAccountNotes:
    def test_updates_notes(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))
        uow.committed = False

        service.update_account_notes(
            UpdateAccountNotes(
                account_id=account.id,
                requesting_user_id=uid,
                notes="New notes",
            )
        )
        assert account.notes == "New notes"
        assert uow.committed

    def test_clears_notes(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid, notes="Old notes"))

        service.update_account_notes(
            UpdateAccountNotes(
                account_id=account.id,
                requesting_user_id=uid,
                notes=None,
            )
        )
        assert account.notes is None

    def test_raises_not_found(self) -> None:
        service, uow = _make_service()
        with pytest.raises(AccountNotFoundError):
            service.update_account_notes(
                UpdateAccountNotes(
                    account_id=uuid.uuid4(),
                    requesting_user_id=uuid.uuid4(),
                    notes="Hello",
                )
            )

    def test_raises_not_owner(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(NotAccountOwnerError):
            service.update_account_notes(
                UpdateAccountNotes(
                    account_id=account.id,
                    requesting_user_id=uuid.uuid4(),
                    notes="Hello",
                )
            )

    def test_rejects_notes_over_500_chars(self) -> None:
        service, uow = _make_service()
        uid = uuid.uuid4()
        account = service.create_account(_make_create_cmd(owner_user_id=uid))

        with pytest.raises(InvalidAccountNotesError):
            service.update_account_notes(
                UpdateAccountNotes(
                    account_id=account.id,
                    requesting_user_id=uid,
                    notes="A" * 501,
                )
            )

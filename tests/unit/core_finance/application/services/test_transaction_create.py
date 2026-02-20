from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
)
from emerald.core_finance.application.services.transaction_management import (
    TransactionManagementService,
)
from emerald.core_finance.domain.events.transaction_events import TransactionCreated
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    InsufficientPermissionError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    DuplicateExternalIdError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import (
    PermissionLevel,
)
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.core_finance.domain.models.value_objects.user_reference import (
    UserReference,
)
from emerald.shared_kernel.domain.exceptions import CurrencyMismatchError
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)
from emerald.shared_kernel.domain.services.retention_policy_service import (
    RetentionPolicyService,
)
from tests.unit.core_finance.fakes import FakeCoreFinanceUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_service() -> tuple[TransactionManagementService, FakeCoreFinanceUnitOfWork]:
    uow = FakeCoreFinanceUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    service = TransactionManagementService(uow=uow, retention_policy_service=retention_service)
    return service, uow


async def _make_account(
    uow: FakeCoreFinanceUnitOfWork,
    owner_id: uuid.UUID | None = None,
    currency: Currency = Currency.USD,
) -> tuple[Account, uuid.UUID]:
    owner_id = owner_id or uuid.uuid4()
    owner = UserReference(user_id=owner_id, display_name="Test Owner")
    account = Account.create(
        owner=owner,
        account_name=AccountName("Test Account"),
        currency=currency,
        opening_balance=Money(Decimal("1000.00"), currency),
        account_type_id=uuid.uuid4(),
        financial_institution_id=uuid.uuid4(),
    )
    await uow.accounts.save(account)
    account.collect_events()  # Clear creation events
    return account, owner_id


def _make_create_cmd(**overrides: Any) -> CreateTransaction:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "requesting_user_id": uuid.uuid4(),
        "transaction_date": date(2024, 1, 15),
        "amount": Decimal("100.00"),
        "currency_code": "USD",
        "original_description": "Test Transaction",
        "import_source_type": "MANUAL",
    }
    defaults.update(overrides)
    return CreateTransaction(**defaults)


class TestCreateTransactionSuccess:
    async def test_creates_manual_transaction(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        txn = await service.create_transaction(cmd)
        assert txn.original_description == "Test Transaction"
        assert txn.import_source.source_type.value == "MANUAL"
        assert txn.review_status == ReviewStatus.TO_REVIEW

    async def test_creates_bank_import_transaction(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            import_source_type="BANK_IMPORT",
            source_id="bank-conn-123",
            external_id="ext-001",
        )
        txn = await service.create_transaction(cmd)
        assert txn.import_source.source_type.value == "BANK_IMPORT"
        assert txn.import_source.source_id == "bank-conn-123"
        assert txn.external_id == "ext-001"

    async def test_returns_transaction_with_correct_fields(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            amount=Decimal("250.50"),
            merchant="Coffee Shop",
            comments="Morning coffee",
            value_date=date(2024, 1, 16),
        )
        txn = await service.create_transaction(cmd)
        assert txn.amount == Money(Decimal("250.50"), Currency.USD)
        assert txn.account_id == account.id
        assert txn.merchant == "Coffee Shop"
        assert txn.comments == "Morning coffee"
        assert txn.transaction_date == date(2024, 1, 15)
        assert txn.value_date == date(2024, 1, 16)

    async def test_zero_amount_allowed(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            amount=Decimal("0"),
        )
        txn = await service.create_transaction(cmd)
        assert txn.amount.amount == Decimal("0")

    async def test_no_external_id_skips_dedup_check(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd1 = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            external_id=None,
        )
        txn1 = await service.create_transaction(cmd1)
        cmd2 = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            external_id=None,
        )
        txn2 = await service.create_transaction(cmd2)
        assert txn1.id != txn2.id

    async def test_editor_can_create(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        editor_id = uuid.uuid4()
        account.share_with(
            user_id=editor_id,
            permission=PermissionLevel.EDITOR,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=editor_id,
            currency_code=account.currency.code,
        )
        txn = await service.create_transaction(cmd)
        assert txn is not None

    async def test_commits_uow(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        uow.committed = False
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        await service.create_transaction(cmd)
        assert uow.committed is True

    async def test_emits_transaction_created_event(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            amount=Decimal("42.00"),
        )
        txn = await service.create_transaction(cmd)
        events = txn.collect_events()
        created_events = [e for e in events if isinstance(e, TransactionCreated)]
        assert len(created_events) == 1
        event = created_events[0]
        assert event.account_id == account.id
        assert event.amount == Decimal("42.00")
        assert event.currency_code == "USD"
        assert event.import_source_type == "MANUAL"
        assert event.created_by == owner_id


class TestCreateTransactionValidation:
    async def test_currency_mismatch_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow, currency=Currency.USD)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code="EUR",
        )
        with pytest.raises(CurrencyMismatchError):
            await service.create_transaction(cmd)

    async def test_duplicate_external_id_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd1 = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            external_id="dup-001",
        )
        await service.create_transaction(cmd1)

        cmd2 = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            external_id="dup-001",
        )
        with pytest.raises(DuplicateExternalIdError):
            await service.create_transaction(cmd2)

    async def test_duplicate_external_id_includes_soft_deleted(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd1 = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            external_id="dup-002",
        )
        txn = await service.create_transaction(cmd1)
        txn.collect_events()

        # Soft-delete the transaction
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        txn.soft_delete(deleted_by=owner_id, retention=retention)
        txn.collect_events()
        await uow.transactions.save(txn)

        # Attempt to create another with the same external_id
        cmd2 = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
            external_id="dup-002",
        )
        with pytest.raises(DuplicateExternalIdError):
            await service.create_transaction(cmd2)

    async def test_account_not_found_raises(self) -> None:
        service, uow = _make_service()
        cmd = _make_create_cmd()
        with pytest.raises(AccountNotFoundError):
            await service.create_transaction(cmd)

    async def test_deleted_account_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        account.soft_delete(deleted_by=owner_id, retention=retention)
        account.collect_events()
        await uow.accounts.save(account)

        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        with pytest.raises(AccountNotActiveError):
            await service.create_transaction(cmd)

    async def test_viewer_permission_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=viewer_id,
            currency_code=account.currency.code,
        )
        with pytest.raises(InsufficientPermissionError):
            await service.create_transaction(cmd)

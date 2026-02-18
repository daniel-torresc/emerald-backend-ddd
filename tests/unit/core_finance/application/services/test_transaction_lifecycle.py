from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
    RecoverTransaction,
    SoftDeleteTransaction,
)
from emerald.core_finance.application.services.transaction_management import (
    TransactionManagementService,
)
from emerald.core_finance.domain.events.transaction_events import (
    TransactionRecovered,
    TransactionSoftDeleted,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    InsufficientPermissionError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    ParentAccountDeletedError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import (
    PermissionLevel,
)
from emerald.core_finance.domain.models.value_objects.user_reference import (
    UserReference,
)
from emerald.shared_kernel.domain.exceptions import (
    AlreadyDeletedError,
    NotDeletedError,
)
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


def _make_account(
    uow: FakeCoreFinanceUnitOfWork,
    owner_id: uuid.UUID | None = None,
) -> tuple[Account, uuid.UUID]:
    owner_id = owner_id or uuid.uuid4()
    owner = UserReference(user_id=owner_id, display_name="Test Owner")
    account = Account.create(
        owner=owner,
        account_name=AccountName("Test Account"),
        currency=Currency.USD,
        opening_balance=Money(Decimal("1000.00"), Currency.USD),
        account_type_id=uuid.uuid4(),
        financial_institution_id=uuid.uuid4(),
    )
    uow.accounts.save(account)
    account.collect_events()
    return account, owner_id


async def _create_transaction(
    service: TransactionManagementService,
    account: Account,
    owner_id: uuid.UUID,
    **overrides: Any,
) -> Transaction:
    defaults: dict[str, Any] = {
        "account_id": account.id,
        "requesting_user_id": owner_id,
        "transaction_date": date(2024, 1, 15),
        "amount": Decimal("100.00"),
        "currency_code": account.currency.code,
        "original_description": "Test Transaction",
        "import_source_type": "MANUAL",
    }
    defaults.update(overrides)
    cmd = CreateTransaction(**defaults)
    txn = await service.create_transaction(cmd)
    txn.collect_events()
    return txn


class TestSoftDeleteTransaction:
    async def test_soft_delete_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(cmd)
        assert txn.is_deleted()
        assert txn.deleted_at is not None
        assert uow.committed is True

    async def test_soft_delete_emits_event(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(cmd)
        events = txn.collect_events()
        deleted_events = [e for e in events if isinstance(e, TransactionSoftDeleted)]
        assert len(deleted_events) == 1
        assert deleted_events[0].deleted_by == owner_id
        assert deleted_events[0].account_id == account.id

    async def test_soft_delete_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
        )
        with pytest.raises(InsufficientPermissionError):
            await service.soft_delete_transaction(cmd)

    async def test_already_deleted_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(cmd)
        txn.collect_events()

        with pytest.raises(AlreadyDeletedError):
            await service.soft_delete_transaction(cmd)

    async def test_soft_delete_with_reason(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            reason="Duplicate entry",
        )
        await service.soft_delete_transaction(cmd)
        assert txn.deletion_reason == "Duplicate entry"


class TestRecoverTransaction:
    async def test_recover_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        delete_cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(delete_cmd)
        txn.collect_events()
        uow.committed = False

        recover_cmd = RecoverTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.recover_transaction(recover_cmd)
        assert not txn.is_deleted()
        assert txn.deleted_at is None
        assert uow.committed is True

    async def test_recover_emits_event(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        delete_cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(delete_cmd)
        txn.collect_events()

        recover_cmd = RecoverTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.recover_transaction(recover_cmd)
        events = txn.collect_events()
        recovered_events = [e for e in events if isinstance(e, TransactionRecovered)]
        assert len(recovered_events) == 1
        assert recovered_events[0].account_id == account.id

    async def test_recover_non_owner_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        editor_id = uuid.uuid4()
        account.share_with(
            user_id=editor_id,
            permission=PermissionLevel.EDITOR,
            granted_by=owner_id,
        )
        account.collect_events()

        txn = await _create_transaction(service, account, owner_id)

        delete_cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(delete_cmd)
        txn.collect_events()

        recover_cmd = RecoverTransaction(
            account_id=account.id,
            requesting_user_id=editor_id,
            transaction_id=txn.id,
        )
        with pytest.raises(InsufficientPermissionError):
            await service.recover_transaction(recover_cmd)

    async def test_recover_parent_account_deleted_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        # Soft-delete the transaction first
        delete_cmd = SoftDeleteTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        await service.soft_delete_transaction(delete_cmd)
        txn.collect_events()

        # Soft-delete the parent account
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        account.soft_delete(deleted_by=owner_id, retention=retention)
        account.collect_events()
        uow.accounts.save(account)

        recover_cmd = RecoverTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        with pytest.raises(ParentAccountDeletedError):
            await service.recover_transaction(recover_cmd)

    async def test_recover_not_deleted_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)

        recover_cmd = RecoverTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        with pytest.raises(NotDeletedError):
            await service.recover_transaction(recover_cmd)

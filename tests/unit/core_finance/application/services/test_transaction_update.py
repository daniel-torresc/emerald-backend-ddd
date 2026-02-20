from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
    UpdateTransactionAmount,
    UpdateTransactionComments,
    UpdateTransactionDates,
    UpdateTransactionDescription,
    UpdateTransactionMerchant,
)
from emerald.core_finance.application.services.transaction_management import (
    TransactionManagementService,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    InsufficientPermissionError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    TransactionNotFoundError,
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


def _soft_delete_transaction(txn: Transaction, deleted_by: uuid.UUID) -> None:
    retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
    txn.soft_delete(deleted_by=deleted_by, retention=retention)
    txn.collect_events()


class TestUpdateDescription:
    async def test_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = UpdateTransactionDescription(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            user_description="Updated desc",
        )
        await service.update_description(cmd)
        assert txn.user_description == "Updated desc"
        assert uow.committed is True

    async def test_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = UpdateTransactionDescription(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
            user_description="Nope",
        )
        with pytest.raises(InsufficientPermissionError):
            await service.update_description(cmd)

    async def test_deleted_transaction_raises_not_found(self) -> None:
        """Soft-deleted txn is filtered by repo (include_deleted=False),
        so service raises TransactionNotFoundError."""
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        _soft_delete_transaction(txn, owner_id)
        await uow.transactions.save(txn)

        cmd = UpdateTransactionDescription(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            user_description="Will fail",
        )
        with pytest.raises(TransactionNotFoundError):
            await service.update_description(cmd)


class TestUpdateMerchant:
    async def test_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = UpdateTransactionMerchant(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            merchant="New Merchant",
        )
        await service.update_merchant(cmd)
        assert txn.merchant == "New Merchant"
        assert uow.committed is True

    async def test_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = UpdateTransactionMerchant(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
            merchant="Nope",
        )
        with pytest.raises(InsufficientPermissionError):
            await service.update_merchant(cmd)


class TestUpdateComments:
    async def test_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = UpdateTransactionComments(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            comments="New comment",
        )
        await service.update_comments(cmd)
        assert txn.comments == "New comment"
        assert uow.committed is True

    async def test_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = UpdateTransactionComments(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
            comments="Nope",
        )
        with pytest.raises(InsufficientPermissionError):
            await service.update_comments(cmd)


class TestUpdateDates:
    async def test_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = UpdateTransactionDates(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            transaction_date=date(2024, 2, 1),
            value_date=date(2024, 2, 2),
        )
        await service.update_dates(cmd)
        assert txn.transaction_date == date(2024, 2, 1)
        assert txn.value_date == date(2024, 2, 2)
        assert uow.committed is True

    async def test_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = UpdateTransactionDates(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
            transaction_date=date(2024, 2, 1),
        )
        with pytest.raises(InsufficientPermissionError):
            await service.update_dates(cmd)


class TestUpdateAmount:
    async def test_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = UpdateTransactionAmount(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            amount=Decimal("999.99"),
            currency_code="USD",
        )
        await service.update_amount(cmd)
        assert txn.amount == Money(Decimal("999.99"), Currency.USD)
        assert uow.committed is True

    async def test_currency_mismatch_raises(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow, currency=Currency.USD)
        txn = await _create_transaction(service, account, owner_id)

        cmd = UpdateTransactionAmount(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
            amount=Decimal("50.00"),
            currency_code="EUR",
        )
        with pytest.raises(CurrencyMismatchError):
            await service.update_amount(cmd)

    async def test_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        txn = await _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        cmd = UpdateTransactionAmount(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
            amount=Decimal("50.00"),
            currency_code="USD",
        )
        with pytest.raises(InsufficientPermissionError):
            await service.update_amount(cmd)


class TestUpdateTransactionNotFound:
    async def test_description_not_found(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)

        cmd = UpdateTransactionDescription(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=uuid.uuid4(),
            user_description="x",
        )
        with pytest.raises(TransactionNotFoundError):
            await service.update_description(cmd)

    async def test_merchant_not_found(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)

        cmd = UpdateTransactionMerchant(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=uuid.uuid4(),
            merchant="x",
        )
        with pytest.raises(TransactionNotFoundError):
            await service.update_merchant(cmd)

    async def test_comments_not_found(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)

        cmd = UpdateTransactionComments(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=uuid.uuid4(),
            comments="x",
        )
        with pytest.raises(TransactionNotFoundError):
            await service.update_comments(cmd)

    async def test_dates_not_found(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)

        cmd = UpdateTransactionDates(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=uuid.uuid4(),
            transaction_date=date(2024, 1, 1),
        )
        with pytest.raises(TransactionNotFoundError):
            await service.update_dates(cmd)

    async def test_amount_not_found(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)

        cmd = UpdateTransactionAmount(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=uuid.uuid4(),
            amount=Decimal("10.00"),
            currency_code="USD",
        )
        with pytest.raises(TransactionNotFoundError):
            await service.update_amount(cmd)

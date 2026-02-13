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
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    TransactionNotFoundError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import (
    PermissionLevel,
)
from emerald.core_finance.domain.models.value_objects.user_reference import (
    UserReference,
)
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.date_range import DateRange
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
    uow.accounts.save(account)
    account.collect_events()
    return account, owner_id


def _create_transaction(
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
    txn = service.create_transaction(cmd)
    txn.collect_events()
    return txn


class TestGetTransaction:
    def test_get_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)

        result = service.get_transaction(
            account_id=account.id,
            transaction_id=txn.id,
            requesting_user_id=owner_id,
        )
        assert result.id == txn.id
        assert result.original_description == "Test Transaction"

    def test_get_not_found(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)

        with pytest.raises(TransactionNotFoundError):
            service.get_transaction(
                account_id=account.id,
                transaction_id=uuid.uuid4(),
                requesting_user_id=owner_id,
            )

    def test_get_viewer_ok(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        result = service.get_transaction(
            account_id=account.id,
            transaction_id=txn.id,
            requesting_user_id=viewer_id,
        )
        assert result.id == txn.id


class TestListTransactions:
    def test_returns_paginated_result(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        _create_transaction(service, account, owner_id, original_description="Txn 1")
        _create_transaction(service, account, owner_id, original_description="Txn 2")
        _create_transaction(service, account, owner_id, original_description="Txn 3")

        result = service.list_transactions(
            account_id=account.id,
            requesting_user_id=owner_id,
        )
        assert result.total == 3
        assert len(result.items) == 3
        assert result.page == 1

    def test_viewer_ok(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        _create_transaction(service, account, owner_id)
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        result = service.list_transactions(
            account_id=account.id,
            requesting_user_id=viewer_id,
        )
        assert result.total == 1

    def test_pagination_works(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        for i in range(5):
            _create_transaction(
                service,
                account,
                owner_id,
                original_description=f"Txn {i}",
            )

        page1 = service.list_transactions(
            account_id=account.id,
            requesting_user_id=owner_id,
            page=1,
            page_size=2,
        )
        assert len(page1.items) == 2
        assert page1.total == 5
        assert page1.has_next is True

        page2 = service.list_transactions(
            account_id=account.id,
            requesting_user_id=owner_id,
            page=2,
            page_size=2,
        )
        assert len(page2.items) == 2
        assert page2.has_previous is True

        page3 = service.list_transactions(
            account_id=account.id,
            requesting_user_id=owner_id,
            page=3,
            page_size=2,
        )
        assert len(page3.items) == 1
        assert page3.has_next is False


class TestListTransactionsInRange:
    def test_filters_by_date_range(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        _create_transaction(
            service,
            account,
            owner_id,
            transaction_date=date(2024, 1, 5),
            original_description="Before range",
        )
        _create_transaction(
            service,
            account,
            owner_id,
            transaction_date=date(2024, 1, 15),
            original_description="In range",
        )
        _create_transaction(
            service,
            account,
            owner_id,
            transaction_date=date(2024, 1, 25),
            original_description="In range too",
        )
        _create_transaction(
            service,
            account,
            owner_id,
            transaction_date=date(2024, 2, 5),
            original_description="After range",
        )

        date_range = DateRange(
            start_date=date(2024, 1, 10),
            end_date=date(2024, 1, 31),
        )
        result = service.list_transactions_in_range(
            account_id=account.id,
            requesting_user_id=owner_id,
            date_range=date_range,
        )
        assert result.total == 2
        descriptions = {t.original_description for t in result.items}
        assert descriptions == {"In range", "In range too"}


class TestCalculateBalance:
    def test_opening_balance_plus_transactions(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        # opening_balance = 1000.00
        _create_transaction(service, account, owner_id, amount=Decimal("500.00"))
        _create_transaction(service, account, owner_id, amount=Decimal("-200.00"))

        balance = service.calculate_balance(
            account_id=account.id,
            requesting_user_id=owner_id,
        )
        # 1000 + 500 + (-200) = 1300
        assert balance == Money(Decimal("1300.00"), Currency.USD)

    def test_viewer_ok(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        _create_transaction(service, account, owner_id, amount=Decimal("100.00"))
        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        balance = service.calculate_balance(
            account_id=account.id,
            requesting_user_id=viewer_id,
        )
        assert balance == Money(Decimal("1100.00"), Currency.USD)

    def test_no_transactions_returns_opening_balance(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)

        balance = service.calculate_balance(
            account_id=account.id,
            requesting_user_id=owner_id,
        )
        assert balance == Money(Decimal("1000.00"), Currency.USD)


class TestGetTransactionCount:
    def test_returns_correct_count(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        _create_transaction(service, account, owner_id)
        _create_transaction(service, account, owner_id)
        _create_transaction(service, account, owner_id)

        count = service.get_transaction_count(
            account_id=account.id,
            requesting_user_id=owner_id,
        )
        assert count == 3

    def test_excludes_deleted(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn1 = _create_transaction(service, account, owner_id)
        _create_transaction(service, account, owner_id)

        # Soft-delete one
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        txn1.soft_delete(deleted_by=owner_id, retention=retention)
        txn1.collect_events()
        uow.transactions.save(txn1)

        count = service.get_transaction_count(
            account_id=account.id,
            requesting_user_id=owner_id,
        )
        assert count == 1

    def test_returns_zero_when_empty(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)

        count = service.get_transaction_count(
            account_id=account.id,
            requesting_user_id=owner_id,
        )
        assert count == 0

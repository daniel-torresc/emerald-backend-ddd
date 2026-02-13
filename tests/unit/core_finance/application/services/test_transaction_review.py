from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
    ReviewTransaction,
    UnreviewTransaction,
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
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import (
    PermissionLevel,
)
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.core_finance.domain.models.value_objects.user_reference import (
    UserReference,
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


class TestReviewTransaction:
    def test_review_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        assert txn.review_status == ReviewStatus.TO_REVIEW
        uow.committed = False

        cmd = ReviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        service.review_transaction(cmd)
        assert txn.review_status == ReviewStatus.REVIEWED
        assert uow.committed is True

    def test_review_viewer_denied(self) -> None:
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

        cmd = ReviewTransaction(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
        )
        with pytest.raises(InsufficientPermissionError):
            service.review_transaction(cmd)

    def test_review_deleted_raises_not_found(self) -> None:
        """Soft-deleted txn is filtered by repo (include_deleted=False),
        so service raises TransactionNotFoundError."""
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        txn.soft_delete(deleted_by=owner_id, retention=retention)
        txn.collect_events()
        uow.transactions.save(txn)

        cmd = ReviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        with pytest.raises(TransactionNotFoundError):
            service.review_transaction(cmd)


class TestUnreviewTransaction:
    def test_unreview_success(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        # First mark as reviewed
        review_cmd = ReviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        service.review_transaction(review_cmd)
        assert txn.review_status == ReviewStatus.REVIEWED
        uow.committed = False

        unreview_cmd = UnreviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        service.unreview_transaction(unreview_cmd)
        assert txn.review_status == ReviewStatus.TO_REVIEW
        assert uow.committed is True

    def test_unreview_viewer_denied(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        review_cmd = ReviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        service.review_transaction(review_cmd)

        viewer_id = uuid.uuid4()
        account.share_with(
            user_id=viewer_id,
            permission=PermissionLevel.VIEWER,
            granted_by=owner_id,
        )
        account.collect_events()

        unreview_cmd = UnreviewTransaction(
            account_id=account.id,
            requesting_user_id=viewer_id,
            transaction_id=txn.id,
        )
        with pytest.raises(InsufficientPermissionError):
            service.unreview_transaction(unreview_cmd)

    def test_unreview_deleted_raises_not_found(self) -> None:
        """Soft-deleted txn is filtered by repo (include_deleted=False),
        so service raises TransactionNotFoundError."""
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        txn.soft_delete(deleted_by=owner_id, retention=retention)
        txn.collect_events()
        uow.transactions.save(txn)

        cmd = UnreviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        with pytest.raises(TransactionNotFoundError):
            service.unreview_transaction(cmd)

    def test_review_commits_uow(self) -> None:
        service, uow = _make_service()
        account, owner_id = _make_account(uow)
        txn = _create_transaction(service, account, owner_id)
        uow.committed = False

        cmd = ReviewTransaction(
            account_id=account.id,
            requesting_user_id=owner_id,
            transaction_id=txn.id,
        )
        service.review_transaction(cmd)
        assert uow.committed is True

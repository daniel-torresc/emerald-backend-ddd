from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import CreateAccount
from emerald.core_finance.application.dtos.commands.bulk_transaction_commands import (
    BulkCreateTransactions,
    BulkDeleteTransactions,
    BulkRecoverTransactions,
    BulkUpdateTransactions,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.application.services.bulk_transaction import (
    BulkTransactionService,
)
from emerald.core_finance.application.services.transaction_management import (
    TransactionManagementService,
)
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.exceptions.bulk_exceptions import (
    BulkLimitExceededError,
    EmptyBulkRequestError,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    InsufficientPermissionError,
)
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.bulk_update_fields import (
    BulkUpdateFields,
)
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.import_source_type import ImportSourceType
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.core_finance.domain.models.value_objects.transaction_input import TransactionInput
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.core_finance.fakes import FakeCoreFinanceUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository

# -- Helpers -------------------------------------------------------------------


def _retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


def _make_services() -> tuple[
    BulkTransactionService,
    AccountManagementService,
    TransactionManagementService,
    FakeCoreFinanceUnitOfWork,
]:
    uow = FakeCoreFinanceUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    bulk_service = BulkTransactionService(uow=uow, retention_policy_service=retention_service)
    acct_service = AccountManagementService(uow=uow, retention_policy_service=retention_service)
    txn_service = TransactionManagementService(uow=uow, retention_policy_service=retention_service)
    return bulk_service, acct_service, txn_service, uow


def _create_account(
    acct_service: AccountManagementService,
    owner_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a test account, return (account_id, owner_id)."""
    user_id = owner_id or uuid.uuid4()
    cmd = CreateAccount(
        owner_user_id=user_id,
        owner_display_name="Test User",
        account_name="Test Account",
        currency_code="USD",
        opening_balance=Decimal("0"),
    )
    account = acct_service.create_account(cmd)
    return account.id, user_id


def _make_input(**overrides: Any) -> TransactionInput:
    defaults: dict[str, Any] = {
        "transaction_date": date(2024, 6, 15),
        "amount": Decimal("100.00"),
        "original_description": "Test transaction",
    }
    defaults.update(overrides)
    return TransactionInput(**defaults)


def _create_transaction(
    uow: FakeCoreFinanceUnitOfWork,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    **overrides: Any,
) -> Transaction:
    """Create a transaction directly via the entity for test setup."""
    defaults: dict[str, Any] = {
        "account_id": account_id,
        "transaction_date": date(2024, 6, 15),
        "amount": Money(Decimal("100.00"), Currency.USD),
        "original_description": "Test",
        "created_by": user_id,
        "import_source": ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        ),
    }
    defaults.update(overrides)
    txn = Transaction.create(**defaults)
    uow.transactions.save(txn)
    return txn


# ==============================================================================
# Request Validation Tests (shared across all operations)
# ==============================================================================


class TestRequestValidation:
    def test_account_not_found_raises(self) -> None:
        svc, _, _, _ = _make_services()
        cmd = BulkCreateTransactions(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transactions=(_make_input(),),
            import_source_type="BULK_IMPORT",
        )
        with pytest.raises(AccountNotFoundError):
            svc.bulk_create_transactions(cmd)

    def test_deleted_account_raises(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        # soft-delete the account
        account = uow.accounts.find_by_id(acct_id, include_deleted=True)
        assert account is not None
        retention = _retention()
        account.soft_delete(deleted_by=user_id, retention=retention)
        uow.accounts.save(account)

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(_make_input(),),
            import_source_type="BULK_IMPORT",
        )
        with pytest.raises(AccountNotActiveError):
            svc.bulk_create_transactions(cmd)

    def test_insufficient_permission_raises(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, _ = _create_account(acct_svc)
        other_user = uuid.uuid4()  # No permission

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=other_user,
            transactions=(_make_input(),),
            import_source_type="BULK_IMPORT",
        )
        with pytest.raises(InsufficientPermissionError):
            svc.bulk_create_transactions(cmd)

    def test_empty_items_raises(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(),
            import_source_type="BULK_IMPORT",
        )
        with pytest.raises(EmptyBulkRequestError):
            svc.bulk_create_transactions(cmd)

    def test_over_1000_items_raises(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        inputs = tuple(_make_input() for _ in range(1001))
        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=inputs,
            import_source_type="BULK_IMPORT",
        )
        with pytest.raises(BulkLimitExceededError):
            svc.bulk_create_transactions(cmd)

    def test_exactly_one_item_succeeds(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(_make_input(),),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        assert result.success_count == 1

    def test_empty_delete_raises(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkDeleteTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(),
        )
        with pytest.raises(EmptyBulkRequestError):
            svc.bulk_delete_transactions(cmd)

    def test_empty_update_raises(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(),
            updates=BulkUpdateFields(review_status=ReviewStatus.REVIEWED),
        )
        with pytest.raises(EmptyBulkRequestError):
            svc.bulk_update_transactions(cmd)

    def test_empty_recover_raises(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(),
        )
        with pytest.raises(EmptyBulkRequestError):
            svc.bulk_recover_transactions(cmd)


# ==============================================================================
# Bulk Create Tests
# ==============================================================================


class TestBulkCreate:
    def test_successful_create_returns_correct_counts(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        inputs = tuple(_make_input(original_description=f"Txn {i}") for i in range(3))
        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=inputs,
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)

        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.total_count == 3
        assert result.is_complete_success is True
        assert len(result.successes) == 3
        # Verify indices
        assert [s.index for s in result.successes] == [0, 1, 2]

    def test_created_transaction_has_correct_data(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        ti = _make_input(
            amount=Decimal("-50.00"),
            merchant="Store",
            comments="Weekly",
        )
        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(ti,),
            import_source_type="BULK_IMPORT",
            source_id="file-001",
        )
        result = svc.bulk_create_transactions(cmd)
        txn = uow.transactions.find_by_id(result.successes[0].entity_id)
        assert txn is not None
        assert txn.account_id == acct_id
        assert txn.amount == Money(Decimal("-50.00"), Currency.USD)
        assert txn.merchant == "Store"
        assert txn.comments == "Weekly"
        assert txn.import_source.source_type == ImportSourceType.BULK_IMPORT
        assert txn.import_source.source_id == "file-001"

    def test_mixed_valid_invalid(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        # Use duplicate external_id to create a mixed valid/invalid batch
        valid = _make_input(external_id="ext-1")
        duplicate = _make_input(external_id="ext-1")  # Duplicate within batch

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(valid, duplicate),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.successes[0].index == 0
        assert result.failures[0].index == 1
        assert result.failures[0].error_code == "DUPLICATE_EXTERNAL_ID"

    def test_within_batch_external_id_dedup(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        inputs = (
            _make_input(external_id="dup", original_description="First"),
            _make_input(external_id="dup", original_description="Second"),
            _make_input(external_id="dup", original_description="Third"),
        )
        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=inputs,
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        assert result.success_count == 1
        assert result.failure_count == 2
        assert result.successes[0].index == 0

    def test_against_existing_external_id_dedup(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        # Create existing transaction with external_id
        _create_transaction(uow, acct_id, user_id, external_id="existing-ext")

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(_make_input(external_id="existing-ext"),),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        assert result.success_count == 0
        assert result.failure_count == 1
        assert result.failures[0].error_code == "DUPLICATE_EXTERNAL_ID"

    def test_all_items_invalid(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        _create_transaction(uow, acct_id, user_id, external_id="dup1")
        _create_transaction(uow, acct_id, user_id, external_id="dup2")

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(
                _make_input(external_id="dup1"),
                _make_input(external_id="dup2"),
            ),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        assert result.success_count == 0
        assert result.failure_count == 2
        assert result.is_complete_failure is True

    def test_bulk_created_event_emitted(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(_make_input(), _make_input()),
            import_source_type="BULK_IMPORT",
        )
        svc.bulk_create_transactions(cmd)

        events = svc.collect_events()
        assert len(events) == 1
        event = events[0]
        from emerald.core_finance.domain.events.transaction_events import TransactionsBulkCreated

        assert isinstance(event, TransactionsBulkCreated)
        assert event.account_id == acct_id
        assert event.success_count == 2
        assert event.failure_count == 0
        assert event.import_source_type == "BULK_IMPORT"
        assert event.created_by == user_id

    def test_individual_events_emitted(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(_make_input(),),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        txn = uow.transactions.find_by_id(result.successes[0].entity_id)
        assert txn is not None
        entity_events = txn.collect_events()
        from emerald.core_finance.domain.events.transaction_events import TransactionCreated

        assert any(isinstance(e, TransactionCreated) for e in entity_events)

    def test_review_status_override(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        ti = _make_input(review_status=ReviewStatus.REVIEWED)
        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(ti,),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        txn = uow.transactions.find_by_id(result.successes[0].entity_id)
        assert txn is not None
        assert txn.review_status == ReviewStatus.REVIEWED

    def test_created_by_set_to_requesting_user(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkCreateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transactions=(_make_input(),),
            import_source_type="BULK_IMPORT",
        )
        result = svc.bulk_create_transactions(cmd)
        txn = uow.transactions.find_by_id(result.successes[0].entity_id)
        assert txn is not None
        assert txn.created_by == user_id


# ==============================================================================
# Bulk Update Tests
# ==============================================================================


class TestBulkUpdate:
    def test_successful_review_status_update(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
            updates=BulkUpdateFields(review_status=ReviewStatus.REVIEWED),
        )
        result = svc.bulk_update_transactions(cmd)

        assert result.success_count == 1
        updated = uow.transactions.find_by_id(txn.id)
        assert updated is not None
        assert updated.review_status == ReviewStatus.REVIEWED

    def test_successful_user_description_update(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
            updates=BulkUpdateFields(user_description="New desc"),
        )
        result = svc.bulk_update_transactions(cmd)

        assert result.success_count == 1
        updated = uow.transactions.find_by_id(txn.id)
        assert updated is not None
        assert updated.user_description == "New desc"

    def test_successful_merchant_update(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
            updates=BulkUpdateFields(merchant="New Merchant"),
        )
        result = svc.bulk_update_transactions(cmd)

        assert result.success_count == 1
        updated = uow.transactions.find_by_id(txn.id)
        assert updated is not None
        assert updated.merchant == "New Merchant"

    def test_clear_merchant_with_none(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id, merchant="Old Merchant")

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
            updates=BulkUpdateFields(merchant=None),
        )
        result = svc.bulk_update_transactions(cmd)

        assert result.success_count == 1
        updated = uow.transactions.find_by_id(txn.id)
        assert updated is not None
        assert updated.merchant is None

    def test_mixed_found_and_not_found(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)
        missing_id = uuid.uuid4()

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id, missing_id),
            updates=BulkUpdateFields(review_status=ReviewStatus.REVIEWED),
        )
        result = svc.bulk_update_transactions(cmd)

        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.failures[0].error_code == "TRANSACTION_NOT_FOUND"
        assert result.failures[0].entity_id == missing_id

    def test_deleted_transaction_fails(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)
        txn.soft_delete(user_id, _retention())
        uow.transactions.save(txn)

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
            updates=BulkUpdateFields(review_status=ReviewStatus.REVIEWED),
        )
        result = svc.bulk_update_transactions(cmd)

        assert result.failure_count == 1
        assert result.failures[0].error_code == "TRANSACTION_DELETED"

    def test_bulk_updated_event_with_fields(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)

        cmd = BulkUpdateTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
            updates=BulkUpdateFields(
                review_status=ReviewStatus.REVIEWED,
                merchant="M",
            ),
        )
        svc.bulk_update_transactions(cmd)

        events = svc.collect_events()
        assert len(events) == 1
        from emerald.core_finance.domain.events.transaction_events import TransactionsBulkUpdated

        event = events[0]
        assert isinstance(event, TransactionsBulkUpdated)
        assert event.updated_fields == frozenset({"review_status", "merchant"})
        assert event.updated_by == user_id


# ==============================================================================
# Bulk Delete Tests
# ==============================================================================


class TestBulkDelete:
    def test_successful_bulk_delete(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn1 = _create_transaction(uow, acct_id, user_id)
        txn2 = _create_transaction(uow, acct_id, user_id)

        cmd = BulkDeleteTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn1.id, txn2.id),
        )
        result = svc.bulk_delete_transactions(cmd)

        assert result.success_count == 2
        assert result.failure_count == 0
        assert uow.transactions.find_by_id(txn1.id) is None  # deleted (not found without flag)
        assert uow.transactions.find_by_id(txn1.id, include_deleted=True) is not None

    def test_already_deleted_fails(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)
        txn.soft_delete(user_id, _retention())
        uow.transactions.save(txn)

        cmd = BulkDeleteTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
        )
        result = svc.bulk_delete_transactions(cmd)

        assert result.failure_count == 1
        assert result.failures[0].error_code == "ALREADY_DELETED"

    def test_not_found_fails(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkDeleteTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(uuid.uuid4(),),
        )
        result = svc.bulk_delete_transactions(cmd)

        assert result.failure_count == 1
        assert result.failures[0].error_code == "TRANSACTION_NOT_FOUND"

    def test_split_parent_cascade_deletes_children(self) -> None:
        svc, acct_svc, txn_svc, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        # Create parent and split it
        parent = _create_transaction(
            uow,
            acct_id,
            user_id,
            amount=Money(Decimal("100.00"), Currency.USD),
        )
        from emerald.core_finance.domain.models.value_objects.split_request import SplitRequest

        children = parent.split(
            [
                SplitRequest(amount=Money(Decimal("60.00"), Currency.USD), description="Part 1"),
                SplitRequest(amount=Money(Decimal("40.00"), Currency.USD), description="Part 2"),
            ],
            user_id,
        )
        uow.transactions.save(parent)
        for child in children:
            uow.transactions.save(child)

        cmd = BulkDeleteTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(parent.id,),
        )
        result = svc.bulk_delete_transactions(cmd)

        # Only parent in result
        assert result.success_count == 1
        assert result.total_count == 1
        # Children also deleted
        for child in children:
            c = uow.transactions.find_by_id(child.id, include_deleted=True)
            assert c is not None
            assert c.is_deleted()

    def test_bulk_deleted_event_emitted(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)

        cmd = BulkDeleteTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
        )
        svc.bulk_delete_transactions(cmd)

        events = svc.collect_events()
        assert len(events) == 1
        from emerald.core_finance.domain.events.transaction_events import TransactionsBulkDeleted

        assert isinstance(events[0], TransactionsBulkDeleted)
        assert events[0].success_count == 1
        assert events[0].deleted_by == user_id


# ==============================================================================
# Bulk Recover Tests
# ==============================================================================


class TestBulkRecover:
    def test_successful_bulk_recover(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)
        txn.soft_delete(user_id, _retention())
        uow.transactions.save(txn)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
        )
        result = svc.bulk_recover_transactions(cmd)

        assert result.success_count == 1
        recovered = uow.transactions.find_by_id(txn.id)
        assert recovered is not None
        assert not recovered.is_deleted()

    def test_requires_owner_permission(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, owner_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, owner_id)
        txn.soft_delete(owner_id, _retention())
        uow.transactions.save(txn)

        # Share with editor
        editor_id = uuid.uuid4()
        account = uow.accounts.find_by_id(acct_id)
        assert account is not None
        account.share_with(editor_id, PermissionLevel.EDITOR, granted_by=owner_id)
        uow.accounts.save(account)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=editor_id,
            transaction_ids=(txn.id,),
        )
        with pytest.raises(InsufficientPermissionError):
            svc.bulk_recover_transactions(cmd)

    def test_non_deleted_fails(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
        )
        result = svc.bulk_recover_transactions(cmd)

        assert result.failure_count == 1
        assert result.failures[0].error_code == "NOT_DELETED"

    def test_split_child_with_deleted_parent_fails(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        # Create parent and split
        parent = _create_transaction(
            uow,
            acct_id,
            user_id,
            amount=Money(Decimal("100.00"), Currency.USD),
        )
        from emerald.core_finance.domain.models.value_objects.split_request import SplitRequest

        children = parent.split(
            [
                SplitRequest(amount=Money(Decimal("60.00"), Currency.USD), description="P1"),
                SplitRequest(amount=Money(Decimal("40.00"), Currency.USD), description="P2"),
            ],
            user_id,
        )
        uow.transactions.save(parent)
        for child in children:
            uow.transactions.save(child)

        # Delete all
        retention = _retention()
        parent.soft_delete(user_id, retention)
        uow.transactions.save(parent)
        for child in children:
            child.soft_delete(user_id, retention)
            uow.transactions.save(child)

        # Try to recover just a child
        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(children[0].id,),
        )
        result = svc.bulk_recover_transactions(cmd)

        assert result.failure_count == 1
        assert result.failures[0].error_code == "PARENT_DELETED"

    def test_split_parent_cascade_recovers_children(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        parent = _create_transaction(
            uow,
            acct_id,
            user_id,
            amount=Money(Decimal("100.00"), Currency.USD),
        )
        from emerald.core_finance.domain.models.value_objects.split_request import SplitRequest

        children = parent.split(
            [
                SplitRequest(amount=Money(Decimal("60.00"), Currency.USD), description="P1"),
                SplitRequest(amount=Money(Decimal("40.00"), Currency.USD), description="P2"),
            ],
            user_id,
        )
        uow.transactions.save(parent)
        for child in children:
            uow.transactions.save(child)

        # Delete all
        retention = _retention()
        for child in children:
            child.soft_delete(user_id, retention)
            uow.transactions.save(child)
        parent.soft_delete(user_id, retention)
        uow.transactions.save(parent)

        # Recover parent
        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(parent.id,),
        )
        result = svc.bulk_recover_transactions(cmd)

        # Only parent in result
        assert result.success_count == 1
        assert result.total_count == 1
        # Children also recovered
        for child in children:
            c = uow.transactions.find_by_id(child.id)
            assert c is not None
            assert not c.is_deleted()

    def test_bulk_recovered_event_emitted(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)
        txn.soft_delete(user_id, _retention())
        uow.transactions.save(txn)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
        )
        svc.bulk_recover_transactions(cmd)

        events = svc.collect_events()
        assert len(events) == 1
        from emerald.core_finance.domain.events.transaction_events import (
            TransactionsBulkRecovered,
        )

        assert isinstance(events[0], TransactionsBulkRecovered)
        assert events[0].success_count == 1
        assert events[0].recovered_by == user_id

    def test_not_found_fails(self) -> None:
        svc, acct_svc, _, _ = _make_services()
        acct_id, user_id = _create_account(acct_svc)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(uuid.uuid4(),),
        )
        result = svc.bulk_recover_transactions(cmd)

        assert result.failure_count == 1
        assert result.failures[0].error_code == "TRANSACTION_NOT_FOUND"

    def test_deleted_account_raises(self) -> None:
        svc, acct_svc, _, uow = _make_services()
        acct_id, user_id = _create_account(acct_svc)
        txn = _create_transaction(uow, acct_id, user_id)
        txn.soft_delete(user_id, _retention())
        uow.transactions.save(txn)

        # Delete account
        account = uow.accounts.find_by_id(acct_id, include_deleted=True)
        assert account is not None
        account.soft_delete(deleted_by=user_id, retention=_retention())
        uow.accounts.save(account)

        cmd = BulkRecoverTransactions(
            account_id=acct_id,
            requesting_user_id=user_id,
            transaction_ids=(txn.id,),
        )
        with pytest.raises(AccountNotActiveError):
            svc.bulk_recover_transactions(cmd)

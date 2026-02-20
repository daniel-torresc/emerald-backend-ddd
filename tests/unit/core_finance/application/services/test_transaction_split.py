from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
    JoinTransactionSplits,
    RecoverTransaction,
    SoftDeleteTransaction,
    SplitTransaction,
    UpdateTransactionAmount,
)
from emerald.core_finance.application.services.transaction_management import (
    TransactionManagementService,
)
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    InsufficientPermissionError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    NotSplitParentError,
    ParentDeletedError,
    SplitAmountMismatchError,
    TransactionNotFoundError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.core_finance.domain.models.value_objects.split_request import SplitRequest
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
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


def _make_create_cmd(**overrides: Any) -> CreateTransaction:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "requesting_user_id": uuid.uuid4(),
        "transaction_date": date(2024, 1, 15),
        "amount": Decimal("-85.00"),
        "currency_code": "USD",
        "original_description": "Supermarket",
        "import_source_type": "MANUAL",
    }
    defaults.update(overrides)
    return CreateTransaction(**defaults)


def _make_split_requests(
    amounts: list[Decimal],
    currency: Currency = Currency.USD,
) -> tuple[SplitRequest, ...]:
    return tuple(
        SplitRequest(
            amount=Money(a, currency),
            description=f"Split {i}",
        )
        for i, a in enumerate(amounts)
    )


# =============================================================================
# split_transaction tests
# =============================================================================


class TestSplitTransactionSuccess:
    async def test_creates_children_and_saves(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        uow.committed = False

        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=parent.id,
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=owner_id,
        )
        children = await service.split_transaction(split_cmd)

        assert len(children) == 2
        assert parent.is_split_parent is True
        assert uow.committed is True

    async def test_children_are_persisted(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)

        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=parent.id,
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=owner_id,
        )
        children = await service.split_transaction(split_cmd)

        for child in children:
            found = await uow.transactions.find_by_id(child.id)
            assert found is not None

    async def test_children_have_correct_review_status(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)

        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=parent.id,
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=owner_id,
        )
        children = await service.split_transaction(split_cmd)
        for child in children:
            assert child.review_status == ReviewStatus.REVIEWED


class TestSplitTransactionPermissions:
    async def test_requires_editor_permission(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)

        viewer_id = uuid.uuid4()
        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=parent.id,
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=viewer_id,
        )
        with pytest.raises(InsufficientPermissionError):
            await service.split_transaction(split_cmd)

    async def test_raises_on_nonexistent_account(self) -> None:
        service, uow = _make_service()
        split_cmd = SplitTransaction(
            account_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=uuid.uuid4(),
        )
        with pytest.raises(AccountNotFoundError):
            await service.split_transaction(split_cmd)

    async def test_raises_on_nonexistent_transaction(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=uuid.uuid4(),
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=owner_id,
        )
        with pytest.raises(TransactionNotFoundError):
            await service.split_transaction(split_cmd)

    async def test_raises_on_deleted_transaction(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=parent.id,
            )
        )

        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=parent.id,
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=owner_id,
        )
        with pytest.raises(TransactionNotFoundError):
            await service.split_transaction(split_cmd)


# =============================================================================
# join_transaction_splits tests
# =============================================================================


class TestJoinTransactionSplitsSuccess:
    async def _setup(
        self,
    ) -> tuple[
        TransactionManagementService,
        FakeCoreFinanceUnitOfWork,
        uuid.UUID,
        uuid.UUID,
        uuid.UUID,
    ]:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        split_cmd = SplitTransaction(
            account_id=account.id,
            transaction_id=parent.id,
            splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
            requesting_user_id=owner_id,
        )
        await service.split_transaction(split_cmd)
        return service, uow, account.id, parent.id, owner_id

    async def test_hard_deletes_children(self) -> None:
        service, uow, account_id, parent_id, owner_id = await self._setup()
        children_before = await uow.transactions.find_children(parent_id)
        assert len(children_before) == 2

        join_cmd = JoinTransactionSplits(
            account_id=account_id,
            transaction_id=parent_id,
            requesting_user_id=owner_id,
        )
        await service.join_transaction_splits(join_cmd)

        children_after = await uow.transactions.find_children(parent_id)
        assert len(children_after) == 0

    async def test_parent_no_longer_split(self) -> None:
        service, uow, account_id, parent_id, owner_id = await self._setup()
        join_cmd = JoinTransactionSplits(
            account_id=account_id,
            transaction_id=parent_id,
            requesting_user_id=owner_id,
        )
        await service.join_transaction_splits(join_cmd)

        parent = await uow.transactions.find_by_id(parent_id)
        assert parent is not None
        assert parent.is_split_parent is False

    async def test_uow_committed(self) -> None:
        service, uow, account_id, parent_id, owner_id = await self._setup()
        uow.committed = False
        join_cmd = JoinTransactionSplits(
            account_id=account_id,
            transaction_id=parent_id,
            requesting_user_id=owner_id,
        )
        await service.join_transaction_splits(join_cmd)
        assert uow.committed is True


class TestJoinTransactionSplitsValidation:
    async def test_requires_editor_permission(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        with pytest.raises(InsufficientPermissionError):
            await service.join_transaction_splits(
                JoinTransactionSplits(
                    account_id=account.id,
                    transaction_id=parent.id,
                    requesting_user_id=uuid.uuid4(),
                )
            )

    async def test_raises_on_non_split_parent(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)

        with pytest.raises(NotSplitParentError):
            await service.join_transaction_splits(
                JoinTransactionSplits(
                    account_id=account.id,
                    transaction_id=parent.id,
                    requesting_user_id=owner_id,
                )
            )

    async def test_raises_on_nonexistent_transaction(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        with pytest.raises(TransactionNotFoundError):
            await service.join_transaction_splits(
                JoinTransactionSplits(
                    account_id=account.id,
                    transaction_id=uuid.uuid4(),
                    requesting_user_id=owner_id,
                )
            )


# =============================================================================
# update_amount split-aware tests
# =============================================================================


class TestUpdateAmountAutoJoin:
    async def test_auto_joins_split_parent(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )
        assert parent.is_split_parent is True

        await service.update_amount(
            UpdateTransactionAmount(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=parent.id,
                amount=Decimal("-100.00"),
                currency_code="USD",
            )
        )

        assert parent.is_split_parent is False
        assert parent.amount == Money(Decimal("-100.00"), Currency.USD)
        children = await uow.transactions.find_children(parent.id)
        assert len(children) == 0


class TestUpdateAmountSplitChildValidation:
    async def test_valid_child_amount_update(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        # Update child 0 from -50 to -60, child 1 stays -35
        # New sum = -60 + -35 = -95 != -85 -> should fail
        with pytest.raises(SplitAmountMismatchError):
            await service.update_amount(
                UpdateTransactionAmount(
                    account_id=account.id,
                    requesting_user_id=owner_id,
                    transaction_id=children[0].id,
                    amount=Decimal("-60.00"),
                    currency_code="USD",
                )
            )

    async def test_valid_child_amount_preserving_sum(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        # Update child 1 to same amount (-35.00): sum = -50 + -35 = -85 = parent
        await service.update_amount(
            UpdateTransactionAmount(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=children[1].id,
                amount=Decimal("-35.00"),
                currency_code="USD",
            )
        )
        # No error means success
        assert children[1].amount == Money(Decimal("-35.00"), Currency.USD)


# =============================================================================
# soft_delete_transaction cascade tests
# =============================================================================


class TestSoftDeleteCascade:
    async def test_deleting_parent_cascades_to_children(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=parent.id,
            )
        )

        assert parent.is_deleted() is True
        for child in children:
            assert child.is_deleted() is True

    async def test_deleting_single_child_does_not_affect_parent(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=children[0].id,
            )
        )

        assert parent.is_deleted() is False
        assert children[0].is_deleted() is True
        assert children[1].is_deleted() is False


# =============================================================================
# recover_transaction cascade tests
# =============================================================================


class TestRecoverCascade:
    async def test_recovering_parent_recovers_deleted_children(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=parent.id,
            )
        )
        assert parent.is_deleted() is True

        await service.recover_transaction(
            RecoverTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=parent.id,
            )
        )

        assert parent.is_deleted() is False
        for child in children:
            assert child.is_deleted() is False

    async def test_recovering_child_raises_when_parent_deleted(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        # Delete parent (cascades to children)
        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=parent.id,
            )
        )

        with pytest.raises(ParentDeletedError):
            await service.recover_transaction(
                RecoverTransaction(
                    account_id=account.id,
                    requesting_user_id=owner_id,
                    transaction_id=children[0].id,
                )
            )

    async def test_recovering_child_succeeds_when_parent_active(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        # Delete only one child
        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=children[0].id,
            )
        )

        # Recover the child -- parent is active, so should succeed
        await service.recover_transaction(
            RecoverTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=children[0].id,
            )
        )
        assert children[0].is_deleted() is False


# =============================================================================
# Balance calculation with splits
# =============================================================================


class TestBalanceWithSplits:
    async def test_balance_unchanged_after_split(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)

        balance_before = await service.calculate_balance(account.id, owner_id)

        await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        balance_after = await service.calculate_balance(account.id, owner_id)
        assert balance_before == balance_after

    async def test_balance_restored_after_join(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)
        balance_before = await service.calculate_balance(account.id, owner_id)

        await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )
        await service.join_transaction_splits(
            JoinTransactionSplits(
                account_id=account.id,
                transaction_id=parent.id,
                requesting_user_id=owner_id,
            )
        )

        balance_after = await service.calculate_balance(account.id, owner_id)
        assert balance_before == balance_after

    async def test_deleting_child_affects_balance(self) -> None:
        service, uow = _make_service()
        account, owner_id = await _make_account(uow)
        cmd = _make_create_cmd(
            account_id=account.id,
            requesting_user_id=owner_id,
            currency_code=account.currency.code,
        )
        parent = await service.create_transaction(cmd)

        children = await service.split_transaction(
            SplitTransaction(
                account_id=account.id,
                transaction_id=parent.id,
                splits=_make_split_requests([Decimal("-50.00"), Decimal("-35.00")]),
                requesting_user_id=owner_id,
            )
        )

        # Delete one child -- parent still excluded, so balance changes
        await service.soft_delete_transaction(
            SoftDeleteTransaction(
                account_id=account.id,
                requesting_user_id=owner_id,
                transaction_id=children[0].id,
            )
        )

        balance_after = await service.calculate_balance(account.id, owner_id)
        # Before: 1000 + (-85) = 915
        # After: 1000 + (-35) = 965 (parent excluded, child 0 deleted, child 1 active)
        assert balance_after == Money(Decimal("965.00"), Currency.USD)

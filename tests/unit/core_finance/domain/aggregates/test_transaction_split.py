from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.transaction_events import (
    TransactionSplit,
    TransactionSplitsJoined,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    AlreadySplitError,
    CannotSplitChildError,
    MaxSplitsExceededError,
    MinimumSplitsRequiredError,
    NotSplitParentError,
    SplitAmountMismatchError,
    TransactionDeletedError,
)
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.import_source_type import ImportSourceType
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.core_finance.domain.models.value_objects.split_request import SplitRequest
from emerald.shared_kernel.domain.exceptions import CurrencyMismatchError
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)

_DEFAULT_IMPORT_SOURCE = ImportSource(
    source_type=ImportSourceType.MANUAL,
    source_id=None,
    imported_at=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
)


def _make_transaction(**overrides: Any) -> Transaction:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "transaction_date": date(2024, 1, 15),
        "amount": Money(Decimal("-85.00"), Currency.USD),
        "original_description": "Supermarket",
        "created_by": uuid.uuid4(),
        "import_source": _DEFAULT_IMPORT_SOURCE,
        "card_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return Transaction.create(**defaults)


def _make_splits_for(
    parent_amount: Money,
    amounts: list[Decimal],
) -> list[SplitRequest]:
    return [
        SplitRequest(
            amount=Money(a, parent_amount.currency),
            description=f"Split {i}",
            merchant=f"Merchant {i}" if i == 0 else None,
            comments=f"Comment {i}" if i == 0 else None,
        )
        for i, a in enumerate(amounts)
    ]


# =============================================================================
# Split operation tests
# =============================================================================


class TestSplitSuccess:
    def test_split_with_two_children(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        split_by = uuid.uuid4()
        children = tx.split(splits, split_by)
        assert len(children) == 2
        assert tx.is_split_parent is True

    def test_split_with_max_children(self) -> None:
        amounts = [Decimal("-1.70")] * 50
        parent_amount = Money(Decimal("-85.00"), Currency.USD)
        tx = _make_transaction(amount=parent_amount)
        splits = _make_splits_for(parent_amount, amounts)
        children = tx.split(splits, uuid.uuid4())
        assert len(children) == 50

    def test_children_inherit_account_id(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.account_id == tx.account_id

    def test_children_inherit_transaction_date(self) -> None:
        tx = _make_transaction(transaction_date=date(2024, 3, 1))
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.transaction_date == date(2024, 3, 1)

    def test_children_inherit_value_date(self) -> None:
        tx = _make_transaction(value_date=date(2024, 3, 5))
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.value_date == date(2024, 3, 5)

    def test_children_inherit_import_source(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.import_source == tx.import_source

    def test_children_inherit_card_id(self) -> None:
        card = uuid.uuid4()
        tx = _make_transaction(card_id=card)
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.card_id == card

    def test_children_have_no_card_id_when_parent_has_none(self) -> None:
        tx = _make_transaction(card_id=None)
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.card_id is None

    def test_children_have_parent_transaction_id(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.parent_transaction_id == tx.id

    def test_children_have_external_id_none(self) -> None:
        tx = _make_transaction(external_id="EXT-001")
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.external_id is None

    def test_children_have_review_status_reviewed(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        for child in children:
            assert child.review_status == ReviewStatus.REVIEWED

    def test_children_have_correct_amounts(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        assert children[0].amount == Money(Decimal("-50.00"), Currency.USD)
        assert children[1].amount == Money(Decimal("-35.00"), Currency.USD)

    def test_children_have_correct_descriptions(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        assert children[0].original_description == "Split 0"
        assert children[1].original_description == "Split 1"

    def test_children_have_correct_merchant_and_comments(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        assert children[0].merchant == "Merchant 0"
        assert children[0].comments == "Comment 0"
        assert children[1].merchant is None
        assert children[1].comments is None

    def test_children_created_by_split_by_user(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        split_by = uuid.uuid4()
        children = tx.split(splits, split_by)
        for child in children:
            assert child.created_by == split_by

    def test_emits_transaction_split_event(self) -> None:
        tx = _make_transaction()
        tx.collect_events()  # clear creation event
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        children = tx.split(splits, uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionSplit)
        assert event.parent_transaction_id == tx.id
        assert event.account_id == tx.account_id
        assert event.child_count == 2
        assert event.child_ids == tuple(c.id for c in children)


class TestSplitEdgeCases:
    def test_zero_amount_splits_when_parent_is_zero(self) -> None:
        tx = _make_transaction(amount=Money(Decimal("0"), Currency.USD))
        splits = [
            SplitRequest(amount=Money(Decimal("0"), Currency.USD), description="A"),
            SplitRequest(amount=Money(Decimal("0"), Currency.USD), description="B"),
        ]
        children = tx.split(splits, uuid.uuid4())
        assert len(children) == 2

    def test_negative_split_amounts_valid_when_sum_matches(self) -> None:
        parent_amount = Money(Decimal("10.00"), Currency.USD)
        tx = _make_transaction(amount=parent_amount)
        splits = [
            SplitRequest(amount=Money(Decimal("20.00"), Currency.USD), description="Main"),
            SplitRequest(amount=Money(Decimal("-10.00"), Currency.USD), description="Rebate"),
        ]
        children = tx.split(splits, uuid.uuid4())
        assert len(children) == 2


class TestSplitValidation:
    def test_raises_when_deleted(self) -> None:
        tx = _make_transaction()
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        tx.soft_delete(uuid.uuid4(), retention)
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        with pytest.raises(TransactionDeletedError):
            tx.split(splits, uuid.uuid4())

    def test_raises_when_split_child(self) -> None:
        tx = _make_transaction(parent_transaction_id=uuid.uuid4())
        splits = [
            SplitRequest(amount=tx.amount, description="A"),
        ]
        with pytest.raises(CannotSplitChildError):
            tx.split(splits, uuid.uuid4())

    def test_raises_when_already_split(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        new_splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        with pytest.raises(AlreadySplitError):
            tx.split(new_splits, uuid.uuid4())

    def test_raises_for_zero_splits(self) -> None:
        tx = _make_transaction()
        with pytest.raises(MinimumSplitsRequiredError):
            tx.split([], uuid.uuid4())

    def test_raises_for_one_split(self) -> None:
        tx = _make_transaction()
        splits = [
            SplitRequest(amount=tx.amount, description="All"),
        ]
        with pytest.raises(MinimumSplitsRequiredError):
            tx.split(splits, uuid.uuid4())

    def test_raises_for_51_splits(self) -> None:
        amounts = [Decimal("-85.00")] + [Decimal("0")] * 50
        parent_amount = Money(Decimal("-85.00"), Currency.USD)
        tx = _make_transaction(amount=parent_amount)
        splits = _make_splits_for(parent_amount, amounts)
        with pytest.raises(MaxSplitsExceededError):
            tx.split(splits, uuid.uuid4())

    def test_raises_for_currency_mismatch(self) -> None:
        tx = _make_transaction(amount=Money(Decimal("-85.00"), Currency.USD))
        splits = [
            SplitRequest(amount=Money(Decimal("-50.00"), Currency.EUR), description="A"),
            SplitRequest(amount=Money(Decimal("-35.00"), Currency.USD), description="B"),
        ]
        with pytest.raises(CurrencyMismatchError):
            tx.split(splits, uuid.uuid4())

    def test_raises_for_sum_mismatch(self) -> None:
        tx = _make_transaction()
        splits = [
            SplitRequest(amount=Money(Decimal("-50.00"), Currency.USD), description="A"),
            SplitRequest(amount=Money(Decimal("-30.00"), Currency.USD), description="B"),
        ]
        with pytest.raises(SplitAmountMismatchError):
            tx.split(splits, uuid.uuid4())


# =============================================================================
# Join operation tests
# =============================================================================


class TestJoinSuccess:
    def test_join_sets_is_split_parent_false(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        assert tx.is_split_parent is True
        tx.join_splits(child_count=2)
        assert tx.is_split_parent is False

    def test_emits_transaction_splits_joined_event(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        tx.collect_events()  # clear split event
        tx.join_splits(child_count=2)
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionSplitsJoined)
        assert event.parent_transaction_id == tx.id
        assert event.account_id == tx.account_id
        assert event.removed_child_count == 2


class TestJoinValidation:
    def test_raises_when_deleted(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        tx.soft_delete(uuid.uuid4(), retention)
        with pytest.raises(TransactionDeletedError):
            tx.join_splits(child_count=2)

    def test_raises_when_not_split_parent(self) -> None:
        tx = _make_transaction()
        with pytest.raises(NotSplitParentError):
            tx.join_splits(child_count=0)


# =============================================================================
# Property tests
# =============================================================================


class TestSplitProperties:
    def test_is_split_parent_false_by_default(self) -> None:
        tx = _make_transaction()
        assert tx.is_split_parent is False

    def test_is_split_parent_true_after_split(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        assert tx.is_split_parent is True

    def test_is_split_parent_false_after_join(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        tx.join_splits(child_count=2)
        assert tx.is_split_parent is False

    def test_is_split_child_unchanged(self) -> None:
        parent_id = uuid.uuid4()
        tx = _make_transaction(parent_transaction_id=parent_id)
        assert tx.is_split_child() is True

    def test_is_split_parent_hydration(self) -> None:
        """Verify is_split_parent can be set via constructor for hydration."""
        tx = Transaction(
            id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            transaction_date=date(2024, 1, 15),
            amount=Money(Decimal("-85.00"), Currency.USD),
            original_description="Test",
            import_source=_DEFAULT_IMPORT_SOURCE,
            is_split_parent=True,
            created_by=uuid.uuid4(),
        )
        assert tx.is_split_parent is True

    def test_create_factory_always_sets_false(self) -> None:
        tx = _make_transaction()
        assert tx.is_split_parent is False


class TestSplitVersionTracking:
    def test_split_increments_version(self) -> None:
        tx = _make_transaction()
        tx.collect_events()
        assert tx.version == 1
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        assert tx.version == 2

    def test_join_splits_increments_version(self) -> None:
        tx = _make_transaction()
        splits = _make_splits_for(tx.amount, [Decimal("-50.00"), Decimal("-35.00")])
        tx.split(splits, uuid.uuid4())
        assert tx.version == 2
        tx.join_splits(child_count=2)
        assert tx.version == 3

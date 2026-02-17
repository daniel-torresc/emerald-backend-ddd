from __future__ import annotations

import dataclasses
import uuid
from decimal import Decimal

import pytest

from emerald.core_finance.domain.events.transaction_events import (
    TransactionCreated,
    TransactionRecovered,
    TransactionReviewed,
    TransactionSoftDeleted,
    TransactionSplit,
    TransactionSplitsJoined,
    TransactionUpdated,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class TestTransactionCreated:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionCreated, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionCreated.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = TransactionCreated(
            aggregate_id=tid,
            account_id=aid,
            amount=Decimal("50.00"),
            currency_code="USD",
            import_source_type="MANUAL",
            created_by=uid,
        )
        assert event.aggregate_id == tid
        assert event.account_id == aid
        assert event.amount == Decimal("50.00")
        assert event.currency_code == "USD"
        assert event.import_source_type == "MANUAL"
        assert event.created_by == uid

    def test_frozen(self) -> None:
        event = TransactionCreated(
            aggregate_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            amount=Decimal("10.00"),
            currency_code="USD",
            import_source_type="MANUAL",
            created_by=uuid.uuid4(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.account_id = uuid.uuid4()  # type: ignore[misc]


class TestTransactionUpdated:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionUpdated, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionUpdated.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = TransactionUpdated(
            aggregate_id=tid,
            account_id=aid,
            updated_by=uid,
            changed_fields=frozenset({"merchant", "comments"}),
        )
        assert event.aggregate_id == tid
        assert event.account_id == aid
        assert event.updated_by == uid
        assert event.changed_fields == frozenset({"merchant", "comments"})

    def test_frozen(self) -> None:
        event = TransactionUpdated(
            aggregate_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            updated_by=uuid.uuid4(),
            changed_fields=frozenset({"amount"}),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.updated_by = uuid.uuid4()  # type: ignore[misc]


class TestTransactionReviewed:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionReviewed, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionReviewed.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = TransactionReviewed(
            aggregate_id=tid,
            account_id=aid,
            reviewed_by=uid,
        )
        assert event.aggregate_id == tid
        assert event.account_id == aid
        assert event.reviewed_by == uid

    def test_frozen(self) -> None:
        event = TransactionReviewed(
            aggregate_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            reviewed_by=uuid.uuid4(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.reviewed_by = uuid.uuid4()  # type: ignore[misc]


class TestTransactionSoftDeleted:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionSoftDeleted, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionSoftDeleted.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = TransactionSoftDeleted(
            aggregate_id=tid,
            account_id=aid,
            deleted_by=uid,
        )
        assert event.aggregate_id == tid
        assert event.account_id == aid
        assert event.deleted_by == uid

    def test_frozen(self) -> None:
        event = TransactionSoftDeleted(
            aggregate_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            deleted_by=uuid.uuid4(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.deleted_by = uuid.uuid4()  # type: ignore[misc]


class TestTransactionRecovered:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionRecovered, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionRecovered.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        aid = uuid.uuid4()
        event = TransactionRecovered(
            aggregate_id=tid,
            account_id=aid,
        )
        assert event.aggregate_id == tid
        assert event.account_id == aid

    def test_frozen(self) -> None:
        event = TransactionRecovered(
            aggregate_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.account_id = uuid.uuid4()  # type: ignore[misc]


class TestTransactionSplit:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionSplit, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionSplit.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        c1, c2 = uuid.uuid4(), uuid.uuid4()
        event = TransactionSplit(
            aggregate_id=tid,
            parent_transaction_id=pid,
            account_id=aid,
            child_count=2,
            child_ids=(c1, c2),
        )
        assert event.aggregate_id == tid
        assert event.parent_transaction_id == pid
        assert event.account_id == aid
        assert event.child_count == 2
        assert event.child_ids == (c1, c2)

    def test_frozen(self) -> None:
        event = TransactionSplit(
            aggregate_id=uuid.uuid4(),
            parent_transaction_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            child_count=2,
            child_ids=(uuid.uuid4(), uuid.uuid4()),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.child_count = 5  # type: ignore[misc]


class TestTransactionSplitsJoined:
    def test_is_domain_event(self) -> None:
        assert issubclass(TransactionSplitsJoined, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert TransactionSplitsJoined.aggregate_type == "transaction"

    def test_fields(self) -> None:
        tid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        event = TransactionSplitsJoined(
            aggregate_id=tid,
            parent_transaction_id=pid,
            account_id=aid,
            removed_child_count=3,
        )
        assert event.aggregate_id == tid
        assert event.parent_transaction_id == pid
        assert event.account_id == aid
        assert event.removed_child_count == 3

    def test_frozen(self) -> None:
        event = TransactionSplitsJoined(
            aggregate_id=uuid.uuid4(),
            parent_transaction_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            removed_child_count=3,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.removed_child_count = 5  # type: ignore[misc]

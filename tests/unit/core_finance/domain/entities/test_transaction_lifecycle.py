from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.transaction_events import (
    TransactionRecovered,
    TransactionSoftDeleted,
)
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import (
    ImportSource,
)
from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
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


def _make_transaction(**overrides: Any) -> Transaction:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "transaction_date": date(2024, 1, 15),
        "amount": Money(Decimal("100.00"), Currency.USD),
        "original_description": "Test Transaction",
        "created_by": uuid.uuid4(),
        "import_source": ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        ),
    }
    defaults.update(overrides)
    tx = Transaction.create(**defaults)
    tx.collect_events()  # clear creation events
    return tx


def _default_retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


class TestTransactionSoftDelete:
    def test_marks_as_deleted(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        assert tx.is_deleted()
        assert not tx.is_active()

    def test_sets_deleted_at(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        assert tx.deleted_at is not None

    def test_sets_deleted_by(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.soft_delete(actor, _default_retention())
        assert tx.deleted_by == actor

    def test_sets_deletion_reason(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention(), reason="Duplicate")
        assert tx.deletion_reason == "Duplicate"

    def test_sets_hard_delete_scheduled_at(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        assert tx.hard_delete_scheduled_at is not None

    def test_emits_transaction_soft_deleted(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.soft_delete(actor, _default_retention())
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionSoftDeleted)
        assert event.aggregate_id == tx.id
        assert event.account_id == tx.account_id
        assert event.deleted_by == actor

    def test_already_deleted_raises(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        with pytest.raises(AlreadyDeletedError):
            tx.soft_delete(uuid.uuid4(), _default_retention())


class TestTransactionRecover:
    def test_clears_deletion_fields(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        tx.collect_events()
        tx.recover()
        assert tx.deleted_at is None
        assert tx.deleted_by is None
        assert tx.deletion_reason is None
        assert tx.hard_delete_scheduled_at is None

    def test_marks_as_active(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        tx.collect_events()
        tx.recover()
        assert tx.is_active()
        assert not tx.is_deleted()

    def test_emits_transaction_recovered(self) -> None:
        tx = _make_transaction()
        tx.soft_delete(uuid.uuid4(), _default_retention())
        tx.collect_events()
        tx.recover()
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionRecovered)
        assert event.aggregate_id == tx.id
        assert event.account_id == tx.account_id

    def test_recover_non_deleted_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(NotDeletedError):
            tx.recover()

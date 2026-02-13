from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from emerald.core_finance.domain.events.transaction_events import (
    TransactionCardLinked,
    TransactionCardUnlinked,
)
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
)
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


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


class TestLinkCard:
    def test_link_emits_card_linked_event(self) -> None:
        tx = _make_transaction()
        card_id = uuid.uuid4()
        tx.update_card_id(card_id)
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionCardLinked)
        assert event.transaction_id == tx.id
        assert event.card_id == card_id
        assert event.account_id == tx.account_id

    def test_link_sets_card_id(self) -> None:
        tx = _make_transaction()
        card_id = uuid.uuid4()
        tx.update_card_id(card_id)
        assert tx.card_id == card_id


class TestRelinkCard:
    def test_relink_to_different_card_emits_event(self) -> None:
        first_card = uuid.uuid4()
        second_card = uuid.uuid4()
        tx = _make_transaction(card_id=first_card)
        tx.update_card_id(second_card)
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionCardLinked)
        assert event.card_id == second_card

    def test_relink_updates_card_id(self) -> None:
        first_card = uuid.uuid4()
        second_card = uuid.uuid4()
        tx = _make_transaction(card_id=first_card)
        tx.update_card_id(second_card)
        assert tx.card_id == second_card


class TestUnlinkCard:
    def test_unlink_emits_card_unlinked_event(self) -> None:
        card_id = uuid.uuid4()
        tx = _make_transaction(card_id=card_id)
        tx.update_card_id(None)
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionCardUnlinked)
        assert event.transaction_id == tx.id
        assert event.previous_card_id == card_id
        assert event.account_id == tx.account_id

    def test_unlink_clears_card_id(self) -> None:
        card_id = uuid.uuid4()
        tx = _make_transaction(card_id=card_id)
        tx.update_card_id(None)
        assert tx.card_id is None


class TestIdempotentLink:
    def test_link_same_card_no_event(self) -> None:
        card_id = uuid.uuid4()
        tx = _make_transaction(card_id=card_id)
        tx.update_card_id(card_id)
        events = tx.collect_events()
        assert len(events) == 0

    def test_link_same_card_no_change(self) -> None:
        card_id = uuid.uuid4()
        tx = _make_transaction(card_id=card_id)
        old_updated_at = tx.updated_at
        tx.update_card_id(card_id)
        assert tx.card_id == card_id
        assert tx.updated_at == old_updated_at


class TestIdempotentUnlink:
    def test_unlink_when_already_none_no_event(self) -> None:
        tx = _make_transaction()
        assert tx.card_id is None
        tx.update_card_id(None)
        events = tx.collect_events()
        assert len(events) == 0

    def test_unlink_when_already_none_no_change(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_card_id(None)
        assert tx.card_id is None
        assert tx.updated_at == old_updated_at


class TestTouchesUpdatedAt:
    def test_link_touches_updated_at(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_card_id(uuid.uuid4())
        assert tx.updated_at >= old_updated_at

    def test_unlink_touches_updated_at(self) -> None:
        card_id = uuid.uuid4()
        tx = _make_transaction(card_id=card_id)
        old_updated_at = tx.updated_at
        tx.update_card_id(None)
        assert tx.updated_at >= old_updated_at

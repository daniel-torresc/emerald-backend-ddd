from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.transaction_events import (
    TransactionUpdated,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import (
    ImportSource,
)
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


class TestUpdateDescription:
    def test_set_description(self) -> None:
        tx = _make_transaction()
        tx.update_description("My custom desc", uuid.uuid4())
        assert tx.user_description == "My custom desc"

    def test_clear_description_with_none(self) -> None:
        tx = _make_transaction()
        tx.update_description("Custom", uuid.uuid4())
        tx.collect_events()
        tx.update_description(None, uuid.uuid4())
        assert tx.user_description is None

    def test_empty_string_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(EmptyDescriptionError):
            tx.update_description("", uuid.uuid4())

    def test_whitespace_only_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(EmptyDescriptionError):
            tx.update_description("   ", uuid.uuid4())

    def test_too_long_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(EmptyDescriptionError):
            tx.update_description("A" * 501, uuid.uuid4())

    def test_trimmed(self) -> None:
        tx = _make_transaction()
        tx.update_description("  Trimmed  ", uuid.uuid4())
        assert tx.user_description == "Trimmed"

    def test_touch_called(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_description("New desc", uuid.uuid4())
        assert tx.updated_at >= old_updated_at

    def test_updated_by_set(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.update_description("New desc", actor)
        assert tx.updated_by == actor

    def test_emits_transaction_updated(self) -> None:
        tx = _make_transaction()
        tx.update_description("New desc", uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUpdated)
        assert event.changed_fields == frozenset({"user_description"})


class TestUpdateMerchant:
    def test_set_merchant(self) -> None:
        tx = _make_transaction()
        tx.update_merchant("Starbucks", uuid.uuid4())
        assert tx.merchant == "Starbucks"

    def test_clear_merchant_with_none(self) -> None:
        tx = _make_transaction(merchant="Old Shop")
        tx.update_merchant(None, uuid.uuid4())
        assert tx.merchant is None

    def test_empty_string_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(InvalidMerchantError):
            tx.update_merchant("", uuid.uuid4())

    def test_whitespace_only_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(InvalidMerchantError):
            tx.update_merchant("   ", uuid.uuid4())

    def test_too_long_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(InvalidMerchantError):
            tx.update_merchant("A" * 201, uuid.uuid4())

    def test_trimmed(self) -> None:
        tx = _make_transaction()
        tx.update_merchant("  Starbucks  ", uuid.uuid4())
        assert tx.merchant == "Starbucks"

    def test_touch_called(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_merchant("Shop", uuid.uuid4())
        assert tx.updated_at >= old_updated_at

    def test_updated_by_set(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.update_merchant("Shop", actor)
        assert tx.updated_by == actor

    def test_emits_transaction_updated(self) -> None:
        tx = _make_transaction()
        tx.update_merchant("Shop", uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUpdated)
        assert event.changed_fields == frozenset({"merchant"})


class TestUpdateComments:
    def test_set_comments(self) -> None:
        tx = _make_transaction()
        tx.update_comments("Nice purchase", uuid.uuid4())
        assert tx.comments == "Nice purchase"

    def test_clear_comments_with_none(self) -> None:
        tx = _make_transaction(comments="Old note")
        tx.update_comments(None, uuid.uuid4())
        assert tx.comments is None

    def test_empty_string_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(InvalidCommentsError):
            tx.update_comments("", uuid.uuid4())

    def test_whitespace_only_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(InvalidCommentsError):
            tx.update_comments("   ", uuid.uuid4())

    def test_too_long_raises(self) -> None:
        tx = _make_transaction()
        with pytest.raises(InvalidCommentsError):
            tx.update_comments("A" * 1001, uuid.uuid4())

    def test_trimmed(self) -> None:
        tx = _make_transaction()
        tx.update_comments("  My note  ", uuid.uuid4())
        assert tx.comments == "My note"

    def test_touch_called(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_comments("Note", uuid.uuid4())
        assert tx.updated_at >= old_updated_at

    def test_updated_by_set(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.update_comments("Note", actor)
        assert tx.updated_by == actor

    def test_emits_transaction_updated(self) -> None:
        tx = _make_transaction()
        tx.update_comments("Note", uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUpdated)
        assert event.changed_fields == frozenset({"comments"})


class TestUpdateDates:
    def test_update_transaction_date_only(self) -> None:
        tx = _make_transaction(transaction_date=date(2024, 1, 15))
        tx.update_dates(uuid.uuid4(), transaction_date=date(2024, 2, 1))
        assert tx.transaction_date == date(2024, 2, 1)

    def test_update_value_date_only(self) -> None:
        tx = _make_transaction()
        tx.update_dates(uuid.uuid4(), value_date=date(2024, 1, 20))
        assert tx.value_date == date(2024, 1, 20)

    def test_update_both_dates(self) -> None:
        tx = _make_transaction(transaction_date=date(2024, 1, 15))
        tx.update_dates(
            uuid.uuid4(),
            transaction_date=date(2024, 3, 1),
            value_date=date(2024, 3, 5),
        )
        assert tx.transaction_date == date(2024, 3, 1)
        assert tx.value_date == date(2024, 3, 5)

    def test_clear_value_date_with_none(self) -> None:
        tx = _make_transaction(value_date=date(2024, 1, 20))
        tx.update_dates(uuid.uuid4(), value_date=None)
        assert tx.value_date is None

    def test_no_change_no_event(self) -> None:
        tx = _make_transaction(transaction_date=date(2024, 1, 15))
        tx.update_dates(uuid.uuid4(), transaction_date=date(2024, 1, 15))
        events = tx.collect_events()
        assert len(events) == 0

    def test_touch_called(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_dates(uuid.uuid4(), transaction_date=date(2024, 6, 1))
        assert tx.updated_at >= old_updated_at

    def test_updated_by_set(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.update_dates(actor, transaction_date=date(2024, 6, 1))
        assert tx.updated_by == actor

    def test_emits_transaction_updated_with_correct_fields(self) -> None:
        tx = _make_transaction(
            transaction_date=date(2024, 1, 15),
            value_date=date(2024, 1, 16),
        )
        tx.update_dates(
            uuid.uuid4(),
            transaction_date=date(2024, 2, 1),
            value_date=date(2024, 2, 5),
        )
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUpdated)
        assert event.changed_fields == frozenset({"transaction_date", "value_date"})

    def test_emits_only_changed_fields(self) -> None:
        tx = _make_transaction(transaction_date=date(2024, 1, 15))
        tx.update_dates(uuid.uuid4(), value_date=date(2024, 1, 20))
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUpdated)
        assert event.changed_fields == frozenset({"value_date"})


class TestUpdateAmount:
    def test_set_new_amount(self) -> None:
        tx = _make_transaction(amount=Money(Decimal("100.00"), Currency.USD))
        new_amount = Money(Decimal("250.00"), Currency.USD)
        tx.update_amount(new_amount, uuid.uuid4())
        assert tx.amount == new_amount

    def test_touch_called(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.update_amount(Money(Decimal("50.00"), Currency.USD), uuid.uuid4())
        assert tx.updated_at >= old_updated_at

    def test_updated_by_set(self) -> None:
        tx = _make_transaction()
        actor = uuid.uuid4()
        tx.update_amount(Money(Decimal("50.00"), Currency.USD), actor)
        assert tx.updated_by == actor

    def test_emits_transaction_updated(self) -> None:
        tx = _make_transaction()
        tx.update_amount(Money(Decimal("50.00"), Currency.USD), uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUpdated)
        assert event.changed_fields == frozenset({"amount"})


class TestVersionTracking:
    def test_update_description_increments_version(self) -> None:
        tx = _make_transaction()
        assert tx.version == 0
        tx.update_description("New desc", uuid.uuid4())
        assert tx.version == 1

    def test_update_merchant_increments_version(self) -> None:
        tx = _make_transaction()
        tx.update_merchant("Starbucks", uuid.uuid4())
        assert tx.version == 1

    def test_update_amount_increments_version(self) -> None:
        tx = _make_transaction()
        tx.update_amount(Money(Decimal("50.00"), Currency.USD), uuid.uuid4())
        assert tx.version == 1

    def test_multiple_updates_increment_version_cumulatively(self) -> None:
        tx = _make_transaction()
        tx.update_description("Desc", uuid.uuid4())
        tx.update_merchant("Shop", uuid.uuid4())
        tx.update_amount(Money(Decimal("50.00"), Currency.USD), uuid.uuid4())
        assert tx.version == 3

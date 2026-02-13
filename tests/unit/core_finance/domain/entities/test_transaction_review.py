from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from emerald.core_finance.domain.events.transaction_events import (
    TransactionReviewed,
)
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import (
    ImportSource,
)
from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
)
from emerald.core_finance.domain.models.value_objects.review_status import (
    ReviewStatus,
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


class TestMarkAsReviewed:
    def test_sets_reviewed_status(self) -> None:
        tx = _make_transaction()
        assert tx.review_status == ReviewStatus.TO_REVIEW
        tx.mark_as_reviewed(uuid.uuid4())
        assert tx.review_status == ReviewStatus.REVIEWED

    def test_emits_transaction_reviewed(self) -> None:
        tx = _make_transaction()
        reviewer = uuid.uuid4()
        tx.mark_as_reviewed(reviewer)
        events = tx.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionReviewed)
        assert event.reviewed_by == reviewer
        assert event.aggregate_id == tx.id
        assert event.account_id == tx.account_id

    def test_already_reviewed_is_noop(self) -> None:
        tx = _make_transaction()
        tx.mark_as_reviewed(uuid.uuid4())
        tx.collect_events()  # clear first review event
        tx.mark_as_reviewed(uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 0
        assert tx.review_status == ReviewStatus.REVIEWED

    def test_updated_by_set(self) -> None:
        tx = _make_transaction()
        reviewer = uuid.uuid4()
        tx.mark_as_reviewed(reviewer)
        assert tx.updated_by == reviewer

    def test_touch_called(self) -> None:
        tx = _make_transaction()
        old_updated_at = tx.updated_at
        tx.mark_as_reviewed(uuid.uuid4())
        assert tx.updated_at >= old_updated_at


class TestMarkForReview:
    def test_sets_to_review_status(self) -> None:
        tx = _make_transaction()
        tx.mark_as_reviewed(uuid.uuid4())
        tx.collect_events()
        tx.mark_for_review(uuid.uuid4())
        assert tx.review_status == ReviewStatus.TO_REVIEW

    def test_already_to_review_is_noop(self) -> None:
        tx = _make_transaction()
        assert tx.review_status == ReviewStatus.TO_REVIEW
        tx.mark_for_review(uuid.uuid4())
        events = tx.collect_events()
        assert len(events) == 0
        assert tx.review_status == ReviewStatus.TO_REVIEW

    def test_updated_by_set_on_transition(self) -> None:
        tx = _make_transaction()
        tx.mark_as_reviewed(uuid.uuid4())
        tx.collect_events()
        actor = uuid.uuid4()
        tx.mark_for_review(actor)
        assert tx.updated_by == actor

import uuid
from dataclasses import dataclass
from datetime import datetime

import pytest

from emerald.shared_kernel.domain.events import DomainEvent


class TestDomainEventBase:
    def test_has_required_attributes(self) -> None:
        agg_id = uuid.uuid4()
        evt = DomainEvent(aggregate_id=agg_id, aggregate_type="Account")
        assert isinstance(evt.event_id, uuid.UUID)
        assert isinstance(evt.occurred_at, datetime)
        assert evt.aggregate_id == agg_id
        assert evt.aggregate_type == "Account"

    def test_event_id_is_unique(self) -> None:
        agg_id = uuid.uuid4()
        a = DomainEvent(aggregate_id=agg_id, aggregate_type="Account")
        b = DomainEvent(aggregate_id=agg_id, aggregate_type="Account")
        assert a.event_id != b.event_id

    def test_occurred_at_is_utc(self) -> None:
        evt = DomainEvent(aggregate_id=uuid.uuid4(), aggregate_type="Test")
        assert evt.occurred_at.tzinfo is not None

    def test_immutable(self) -> None:
        evt = DomainEvent(aggregate_id=uuid.uuid4(), aggregate_type="Test")
        with pytest.raises(AttributeError):
            evt.aggregate_type = "Modified"  # type: ignore[misc]

    def test_events_with_different_id_not_equal(self) -> None:
        agg_id = uuid.uuid4()
        a = DomainEvent(aggregate_id=agg_id, aggregate_type="Account")
        b = DomainEvent(aggregate_id=agg_id, aggregate_type="Account")
        assert a != b


class TestConcreteEvent:
    def test_subclass_inherits_base_attributes(self) -> None:
        @dataclass(frozen=True)
        class AccountCreated(DomainEvent):
            account_name: str = ""

        agg_id = uuid.uuid4()
        evt = AccountCreated(
            aggregate_id=agg_id,
            aggregate_type="Account",
            account_name="Savings",
        )
        assert isinstance(evt.event_id, uuid.UUID)
        assert evt.aggregate_id == agg_id
        assert evt.aggregate_type == "Account"
        assert evt.account_name == "Savings"

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import pytest

from emerald.shared_kernel.domain.events import DomainEvent


@dataclass(frozen=True)
class _AccountEvent(DomainEvent):
    aggregate_type: ClassVar[str] = "Account"


@dataclass(frozen=True)
class _TestEvent(DomainEvent):
    aggregate_type: ClassVar[str] = "Test"


class TestDomainEventBase:
    def test_has_required_attributes(self) -> None:
        agg_id = uuid.uuid4()
        evt = _AccountEvent(aggregate_id=agg_id)
        assert isinstance(evt.event_id, uuid.UUID)
        assert isinstance(evt.occurred_at, datetime)
        assert evt.aggregate_id == agg_id
        assert evt.aggregate_type == "Account"

    def test_event_id_is_unique(self) -> None:
        agg_id = uuid.uuid4()
        a = _AccountEvent(aggregate_id=agg_id)
        b = _AccountEvent(aggregate_id=agg_id)
        assert a.event_id != b.event_id

    def test_occurred_at_is_utc(self) -> None:
        evt = _TestEvent(aggregate_id=uuid.uuid4())
        assert evt.occurred_at.tzinfo is not None

    def test_immutable(self) -> None:
        evt = _TestEvent(aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            evt.aggregate_type = "Modified"  # type: ignore[misc]

    def test_events_with_different_id_not_equal(self) -> None:
        agg_id = uuid.uuid4()
        a = _AccountEvent(aggregate_id=agg_id)
        b = _AccountEvent(aggregate_id=agg_id)
        assert a != b


class TestConcreteEvent:
    def test_subclass_inherits_base_attributes(self) -> None:
        @dataclass(frozen=True)
        class AccountCreated(DomainEvent):
            aggregate_type: ClassVar[str] = "Account"
            account_name: str = ""

        agg_id = uuid.uuid4()
        evt = AccountCreated(
            aggregate_id=agg_id,
            account_name="Savings",
        )
        assert isinstance(evt.event_id, uuid.UUID)
        assert evt.aggregate_id == agg_id
        assert evt.aggregate_type == "Account"
        assert evt.account_name == "Savings"

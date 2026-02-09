import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import pytest

from emerald.shared_kernel.domain.events import DomainEvent
from emerald.shared_kernel.domain.models import AggregateRoot


@dataclass(frozen=True)
class _TestEvent(DomainEvent):
    aggregate_type: ClassVar[str] = "Test"
    detail: str = ""


class TestAggregateRootAttributes:
    def test_has_id(self) -> None:
        ar = AggregateRoot()
        assert isinstance(ar.id, uuid.UUID)

    def test_has_created_at(self) -> None:
        ar = AggregateRoot()
        assert isinstance(ar.created_at, datetime)

    def test_has_updated_at(self) -> None:
        ar = AggregateRoot()
        assert isinstance(ar.updated_at, datetime)

    def test_identity_equality(self) -> None:
        shared_id = uuid.uuid4()
        a = AggregateRoot(id=shared_id)
        b = AggregateRoot(id=shared_id)
        assert a == b


class TestAggregateRootEvents:
    def test_register_event(self) -> None:
        ar = AggregateRoot()
        event = _TestEvent(aggregate_id=ar.id, detail="created")
        ar._register_event(event)
        events = ar.collect_events()
        assert len(events) == 1
        assert events[0] is event

    def test_events_returned_in_order(self) -> None:
        ar = AggregateRoot()
        e1 = _TestEvent(aggregate_id=ar.id, detail="first")
        e2 = _TestEvent(aggregate_id=ar.id, detail="second")
        e3 = _TestEvent(aggregate_id=ar.id, detail="third")
        ar._register_event(e1)
        ar._register_event(e2)
        ar._register_event(e3)
        events = ar.collect_events()
        details = [e.detail for e in events if isinstance(e, _TestEvent)]
        assert details == ["first", "second", "third"]

    def test_collect_clears_events(self) -> None:
        ar = AggregateRoot()
        ar._register_event(_TestEvent(aggregate_id=ar.id, detail="x"))
        ar.collect_events()
        assert ar.collect_events() == []

    def test_second_collect_without_new_events_returns_empty(self) -> None:
        ar = AggregateRoot()
        ar._register_event(_TestEvent(aggregate_id=ar.id, detail="x"))
        ar.collect_events()
        assert ar.collect_events() == []

    def test_no_events_initially(self) -> None:
        ar = AggregateRoot()
        assert ar.collect_events() == []


class TestAggregateRootVersion:
    def test_version_starts_at_zero(self) -> None:
        ar = AggregateRoot()
        assert ar.version == 0

    def test_version_provided_via_kwarg(self) -> None:
        ar = AggregateRoot(version=5)
        assert ar.version == 5

    def test_increment_version_increases_by_one(self) -> None:
        ar = AggregateRoot()
        ar._increment_version()
        assert ar.version == 1
        ar._increment_version()
        assert ar.version == 2

    def test_touch_increments_version(self) -> None:
        ar = AggregateRoot()
        ar._touch()
        assert ar.version == 1

    def test_touch_also_updates_timestamp(self) -> None:
        ar = AggregateRoot()
        original_updated = ar.updated_at
        ar._touch()
        assert ar.updated_at >= original_updated
        assert ar.version == 1

    def test_version_is_read_only_property(self) -> None:
        ar = AggregateRoot()
        with pytest.raises(AttributeError):
            ar.version = 42  # type: ignore[misc]

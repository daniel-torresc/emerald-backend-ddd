import uuid
from dataclasses import dataclass
from datetime import datetime

from emerald.shared_kernel.entities import AggregateRoot
from emerald.shared_kernel.events import DomainEvent


@dataclass(frozen=True)
class _TestEvent(DomainEvent):
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
        event = _TestEvent(aggregate_id=ar.id, aggregate_type="Test", detail="created")
        ar._register_event(event)
        events = ar.collect_events()
        assert len(events) == 1
        assert events[0] is event

    def test_events_returned_in_order(self) -> None:
        ar = AggregateRoot()
        e1 = _TestEvent(aggregate_id=ar.id, aggregate_type="Test", detail="first")
        e2 = _TestEvent(aggregate_id=ar.id, aggregate_type="Test", detail="second")
        e3 = _TestEvent(aggregate_id=ar.id, aggregate_type="Test", detail="third")
        ar._register_event(e1)
        ar._register_event(e2)
        ar._register_event(e3)
        events = ar.collect_events()
        details = [e.detail for e in events if isinstance(e, _TestEvent)]
        assert details == ["first", "second", "third"]

    def test_collect_clears_events(self) -> None:
        ar = AggregateRoot()
        ar._register_event(_TestEvent(aggregate_id=ar.id, aggregate_type="Test", detail="x"))
        ar.collect_events()
        assert ar.collect_events() == []

    def test_second_collect_without_new_events_returns_empty(self) -> None:
        ar = AggregateRoot()
        ar._register_event(_TestEvent(aggregate_id=ar.id, aggregate_type="Test", detail="x"))
        ar.collect_events()
        assert ar.collect_events() == []

    def test_no_events_initially(self) -> None:
        ar = AggregateRoot()
        assert ar.collect_events() == []

from typing import Any

from emerald.shared_kernel.entities.entity import Entity
from emerald.shared_kernel.entities.timestamped import TimestampedMixin
from emerald.shared_kernel.events.domain_event import DomainEvent


class AggregateRoot(TimestampedMixin, Entity):
    """Base for all aggregate roots — combines Identity + Timestamps + event collection."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._events: list[DomainEvent] = []

    def _register_event(self, event: DomainEvent) -> None:
        """Add an event to the internal collection."""
        self._events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """Return all accumulated events and clear the internal list."""
        events = list(self._events)
        self._events.clear()
        return events

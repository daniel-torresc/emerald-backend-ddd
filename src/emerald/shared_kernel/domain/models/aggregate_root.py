from typing import Any

from emerald.shared_kernel.domain.events.domain_event import DomainEvent
from emerald.shared_kernel.domain.models.entity import Entity
from emerald.shared_kernel.domain.models.timestamped import TimestampedMixin


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

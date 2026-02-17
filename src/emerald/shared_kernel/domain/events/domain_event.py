import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base domain event — immutable record of something that happened."""

    aggregate_id: uuid.UUID
    aggregate_type: ClassVar[str]
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

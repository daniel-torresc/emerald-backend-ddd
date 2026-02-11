import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class HardDeleteTrigger(Enum):
    """What initiated the hard delete."""

    USER_INITIATED = "USER_INITIATED"
    AUTOMATIC = "AUTOMATIC"
    ADMIN_INITIATED = "ADMIN_INITIATED"


class RetentionWarningType(Enum):
    """Type of retention warning before automatic hard delete."""

    FIRST_WARNING = "FIRST_WARNING"
    FINAL_WARNING = "FINAL_WARNING"


@dataclass(frozen=True)
class EntitySoftDeleted(DomainEvent):
    """Emitted when an entity is soft deleted."""

    aggregate_type: ClassVar[str] = "data_lifecycle"
    entity_type: DeletableEntityType = DeletableEntityType.USER  # placeholder default
    entity_id: uuid.UUID = uuid.UUID(int=0)  # placeholder default
    deleted_by: uuid.UUID = uuid.UUID(int=0)  # placeholder default
    reason: str | None = None
    hard_delete_scheduled_at: datetime | None = None


@dataclass(frozen=True)
class EntityRecovered(DomainEvent):
    """Emitted when an entity is recovered from trash."""

    aggregate_type: ClassVar[str] = "data_lifecycle"
    entity_type: DeletableEntityType = DeletableEntityType.USER
    entity_id: uuid.UUID = uuid.UUID(int=0)
    recovered_by: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class HardDeleteScheduled(DomainEvent):
    """Emitted when a user confirms hard delete and cooling-off starts."""

    aggregate_type: ClassVar[str] = "data_lifecycle"
    entity_type: DeletableEntityType = DeletableEntityType.USER
    entity_id: uuid.UUID = uuid.UUID(int=0)
    scheduled_at: datetime | None = None
    confirmed_by: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class HardDeleteCancelled(DomainEvent):
    """Emitted when a user cancels during cooling-off period."""

    aggregate_type: ClassVar[str] = "data_lifecycle"
    entity_type: DeletableEntityType = DeletableEntityType.USER
    entity_id: uuid.UUID = uuid.UUID(int=0)
    cancelled_by: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class EntityHardDeleted(DomainEvent):
    """Emitted when an entity is permanently removed."""

    aggregate_type: ClassVar[str] = "data_lifecycle"
    entity_type: DeletableEntityType = DeletableEntityType.USER
    entity_id: uuid.UUID = uuid.UUID(int=0)
    trigger: HardDeleteTrigger = HardDeleteTrigger.AUTOMATIC


@dataclass(frozen=True)
class RetentionWarningDue(DomainEvent):
    """Emitted when approaching automatic hard delete."""

    aggregate_type: ClassVar[str] = "data_lifecycle"
    entity_type: DeletableEntityType = DeletableEntityType.USER
    entity_id: uuid.UUID = uuid.UUID(int=0)
    user_id: uuid.UUID = uuid.UUID(int=0)
    hard_delete_at: datetime | None = None
    warning_type: RetentionWarningType = RetentionWarningType.FIRST_WARNING

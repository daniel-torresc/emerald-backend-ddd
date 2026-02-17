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


@dataclass(frozen=True, kw_only=True)
class LifecycleEvent(DomainEvent):
    """Base event for data lifecycle operations."""

    aggregate_type: ClassVar[str] = "data_lifecycle"


@dataclass(frozen=True)
class EntitySoftDeleted(LifecycleEvent):
    """Emitted when an entity is soft deleted."""

    entity_type: DeletableEntityType
    entity_id: uuid.UUID
    deleted_by: uuid.UUID
    reason: str | None = None
    hard_delete_scheduled_at: datetime | None = None


@dataclass(frozen=True)
class EntityRecovered(LifecycleEvent):
    """Emitted when an entity is recovered from trash."""

    entity_type: DeletableEntityType
    entity_id: uuid.UUID
    recovered_by: uuid.UUID


@dataclass(frozen=True)
class HardDeleteScheduled(LifecycleEvent):
    """Emitted when a user confirms hard delete and cooling-off starts."""

    entity_type: DeletableEntityType
    entity_id: uuid.UUID
    confirmed_by: uuid.UUID
    scheduled_at: datetime | None = None


@dataclass(frozen=True)
class HardDeleteCancelled(LifecycleEvent):
    """Emitted when a user cancels during cooling-off period."""

    entity_type: DeletableEntityType
    entity_id: uuid.UUID
    cancelled_by: uuid.UUID


@dataclass(frozen=True)
class EntityHardDeleted(LifecycleEvent):
    """Emitted when an entity is permanently removed."""

    entity_type: DeletableEntityType
    entity_id: uuid.UUID
    trigger: HardDeleteTrigger = HardDeleteTrigger.AUTOMATIC


@dataclass(frozen=True)
class RetentionWarningDue(LifecycleEvent):
    """Emitted when approaching automatic hard delete."""

    entity_type: DeletableEntityType
    entity_id: uuid.UUID
    user_id: uuid.UUID
    warning_type: RetentionWarningType = RetentionWarningType.FIRST_WARNING
    hard_delete_at: datetime | None = None

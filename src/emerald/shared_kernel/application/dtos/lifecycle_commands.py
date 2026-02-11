import uuid
from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.hard_delete_confirmation import (
    HardDeleteConfirmation,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod


@dataclass(frozen=True)
class SoftDeleteEntity(Command):
    """Command to soft delete an entity."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    deleted_by: uuid.UUID
    reason: str | None = None


@dataclass(frozen=True)
class RecoverEntity(Command):
    """Command to recover an entity from trash."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    recovered_by: uuid.UUID


@dataclass(frozen=True)
class RequestHardDelete(Command):
    """Command to request hard delete (returns cascade summary)."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    requested_by: uuid.UUID


@dataclass(frozen=True)
class ConfirmHardDelete(Command):
    """Command to confirm hard delete with cascade acknowledgment."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    confirmation: HardDeleteConfirmation


@dataclass(frozen=True)
class CancelHardDelete(Command):
    """Command to cancel a pending hard delete during cooling-off."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    cancelled_by: uuid.UUID


@dataclass(frozen=True)
class SetUserRetentionPreference(Command):
    """Command to set a user's retention preference for an entity type."""

    user_id: uuid.UUID
    entity_type: DeletableEntityType
    retention_period: RetentionPeriod

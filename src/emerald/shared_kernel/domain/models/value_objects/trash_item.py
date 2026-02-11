import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


@dataclass(frozen=True)
class TrashItem:
    """Read-model representation of a soft-deleted entity in the trash view."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    display_name: str
    deleted_at: datetime
    deleted_by: uuid.UUID
    deletion_reason: str | None
    hard_delete_scheduled_at: datetime
    child_count: int

    def __post_init__(self) -> None:
        if self.child_count < 0:
            raise InvalidValueError(f"child_count must be >= 0, got {self.child_count}")
        if not self.display_name.strip():
            raise InvalidValueError("display_name must not be empty or blank")

    @property
    def time_remaining(self) -> timedelta:
        """Time until hard delete. May be negative if overdue."""
        return self.hard_delete_scheduled_at - datetime.now(UTC)

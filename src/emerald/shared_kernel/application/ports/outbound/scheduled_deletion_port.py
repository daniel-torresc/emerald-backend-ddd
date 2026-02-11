import uuid
from datetime import datetime
from typing import Protocol

from emerald.shared_kernel.domain.events.lifecycle_events import RetentionWarningType
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class ScheduledDeletionPort(Protocol):
    """Port for querying entities due for hard delete or retention warning."""

    def find_due_for_hard_delete(
        self, as_of: datetime
    ) -> list[tuple[DeletableEntityType, uuid.UUID]]: ...

    def find_due_for_warning(
        self, warning_type: RetentionWarningType, as_of: datetime
    ) -> list[tuple[DeletableEntityType, uuid.UUID, uuid.UUID]]: ...

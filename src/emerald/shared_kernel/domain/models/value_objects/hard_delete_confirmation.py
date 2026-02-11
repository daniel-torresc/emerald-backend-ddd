import uuid
from dataclasses import dataclass
from datetime import datetime

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


@dataclass(frozen=True)
class HardDeleteConfirmation:
    """User acknowledgment of a hard delete and its cascade impact."""

    entity_id: uuid.UUID
    entity_type: DeletableEntityType
    confirmed_by: uuid.UUID
    acknowledged_cascade_count: int
    confirmed_at: datetime

    def __post_init__(self) -> None:
        if self.acknowledged_cascade_count < 1:
            raise InvalidValueError(
                f"acknowledged_cascade_count must be >= 1, got {self.acknowledged_cascade_count}"
            )

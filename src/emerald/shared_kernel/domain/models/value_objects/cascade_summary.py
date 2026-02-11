import uuid
from dataclasses import dataclass

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.trash_item import TrashItem


@dataclass(frozen=True)
class CascadeSummary:
    """Summary of entities affected by a hard delete cascade."""

    target_entity_id: uuid.UUID
    target_entity_type: DeletableEntityType
    affected_children: tuple[TrashItem, ...]
    total_affected_count: int

    def __post_init__(self) -> None:
        if self.total_affected_count < 1:
            raise InvalidValueError(
                f"total_affected_count must be >= 1 (includes the target), "
                f"got {self.total_affected_count}"
            )

import uuid
from typing import Protocol

from emerald.shared_kernel.domain.models.value_objects.cascade_summary import CascadeSummary
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.paginated_result import PaginatedResult
from emerald.shared_kernel.domain.models.value_objects.trash_item import TrashItem


class TrashQueryPort(Protocol):
    """Port for querying trash items and cascade summaries."""

    def list_trash(
        self,
        user_id: uuid.UUID,
        entity_type: DeletableEntityType | None = None,
        sort_by: str = "deleted_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult[TrashItem]: ...

    def get_cascade_summary(
        self, entity_id: uuid.UUID, entity_type: DeletableEntityType
    ) -> CascadeSummary: ...

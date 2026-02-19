import uuid
from typing import Protocol

from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName


class TaxonomyRepository(Protocol):
    """Port for taxonomy persistence."""

    async def save(self, taxonomy: Taxonomy) -> None: ...

    async def find_by_id(
        self, taxonomy_id: uuid.UUID, include_deleted: bool = False
    ) -> Taxonomy | None: ...

    async def find_by_owner(
        self, owner_id: uuid.UUID, include_deleted: bool = False
    ) -> list[Taxonomy]: ...

    async def exists_by_name_for_owner(
        self,
        name: TaxonomyName,
        owner_id: uuid.UUID,
        exclude_taxonomy_id: uuid.UUID | None = None,
    ) -> bool: ...

    async def find_by_term_id(self, term_id: uuid.UUID) -> Taxonomy | None:
        """Find the taxonomy that contains a given term (active taxonomies only)."""
        ...

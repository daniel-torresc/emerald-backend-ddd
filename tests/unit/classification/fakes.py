from __future__ import annotations

import uuid
from collections.abc import Iterator

from emerald.classification.application.ports.outbound.unit_of_work import (
    AbstractClassificationUnitOfWork,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class FakeTaxonomyRepository:
    """In-memory taxonomy repository for tests."""

    def __init__(self) -> None:
        self._taxonomies: dict[uuid.UUID, Taxonomy] = {}
        self.seen: set[Taxonomy] = set()

    def save(self, taxonomy: Taxonomy) -> None:
        self._taxonomies[taxonomy.id] = taxonomy
        self.seen.add(taxonomy)

    def find_by_id(self, taxonomy_id: uuid.UUID, include_deleted: bool = False) -> Taxonomy | None:
        taxonomy = self._taxonomies.get(taxonomy_id)
        if taxonomy is None:
            return None
        self.seen.add(taxonomy)
        if not include_deleted and taxonomy.is_deleted():
            return None
        return taxonomy

    def find_by_owner(self, owner_id: uuid.UUID, include_deleted: bool = False) -> list[Taxonomy]:
        results: list[Taxonomy] = []
        for taxonomy in self._taxonomies.values():
            if taxonomy.owner_id != owner_id:
                continue
            if not include_deleted and taxonomy.is_deleted():
                continue
            self.seen.add(taxonomy)
            results.append(taxonomy)
        return results

    def exists_by_name_for_owner(
        self,
        name: TaxonomyName,
        owner_id: uuid.UUID,
        exclude_taxonomy_id: uuid.UUID | None = None,
    ) -> bool:
        for taxonomy in self._taxonomies.values():
            if taxonomy.is_deleted():
                continue
            if taxonomy.owner_id != owner_id:
                continue
            if exclude_taxonomy_id is not None and taxonomy.id == exclude_taxonomy_id:
                continue
            if taxonomy.name == name:
                return True
        return False


class FakeClassificationUnitOfWork(AbstractClassificationUnitOfWork):
    """In-memory Unit of Work for Classification tests."""

    taxonomies: FakeTaxonomyRepository

    def __init__(self) -> None:
        self.taxonomies = FakeTaxonomyRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def collect_new_events(self) -> Iterator[DomainEvent]:
        for taxonomy in self.taxonomies.seen:
            yield from taxonomy.collect_events()

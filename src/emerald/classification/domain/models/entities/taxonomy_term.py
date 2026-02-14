from __future__ import annotations

import uuid
from typing import Any

from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.shared_kernel.domain.models.base.entity import Entity
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin
from emerald.shared_kernel.domain.models.base.timestamped import TimestampedMixin


class TaxonomyTerm(SoftDeletableMixin, TimestampedMixin, Entity):
    """Child entity managed inside the Taxonomy aggregate."""

    def __init__(
        self,
        *,
        taxonomy_id: uuid.UUID,
        name: TermName,
        description: str | None = None,
        parent_term_id: uuid.UUID | None = None,
        sort_order: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._taxonomy_id = taxonomy_id
        self.name = name
        self.description = description
        self.parent_term_id = parent_term_id
        self.sort_order = sort_order

    @property
    def taxonomy_id(self) -> uuid.UUID:
        return self._taxonomy_id

    # -- Internal mutation methods (called only by Taxonomy aggregate) ----------

    def _rename(self, new_name: TermName) -> None:
        self.name = new_name
        self._touch()

    def _update_description(self, description: str | None) -> None:
        self.description = description
        self._touch()

    def _move(self, new_parent_id: uuid.UUID | None) -> None:
        self.parent_term_id = new_parent_id
        self._touch()

    def _set_sort_order(self, order: int) -> None:
        self.sort_order = order

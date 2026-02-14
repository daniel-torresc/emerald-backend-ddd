from __future__ import annotations

import uuid
from typing import Any

from emerald.classification.domain.constants import (
    MAX_TAXONOMY_DESCRIPTION_LENGTH,
    MAX_TERM_DESCRIPTION_LENGTH,
    MAX_TERMS_PER_TAXONOMY,
)
from emerald.classification.domain.events.taxonomy_events import (
    TaxonomyCreated,
    TaxonomyDescriptionUpdated,
    TaxonomyRecovered,
    TaxonomyRenamed,
    TaxonomySoftDeleted,
    TermAdded,
    TermDeleted,
    TermDescriptionUpdated,
    TermMoved,
    TermRecovered,
    TermRenamed,
    TermsReordered,
)
from emerald.classification.domain.exceptions import (
    CannotBeOwnParentError,
    CircularReferenceError,
    IncompleteReorderError,
    MaxTermsExceededError,
    ParentTermDeletedError,
    ParentTermNotFoundError,
    TaxonomyDescriptionTooLongError,
    TaxonomyNotActiveError,
    TermDescriptionTooLongError,
    TermNameAlreadyExistsError,
    TermNotFoundError,
)
from emerald.classification.domain.models.entities.taxonomy_term import TaxonomyTerm
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.classification.domain.models.value_objects.taxonomy_path import TaxonomyPath
from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.shared_kernel.domain.models.base.aggregate_root import AggregateRoot
from emerald.shared_kernel.domain.models.base.auditable import AuditableMixin
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod


class Taxonomy(SoftDeletableMixin, AuditableMixin, AggregateRoot):
    """Taxonomy aggregate root — user-owned hierarchical classification system."""

    def __init__(
        self,
        *,
        owner_id: uuid.UUID,
        name: TaxonomyName,
        description: str | None = None,
        terms: list[TaxonomyTerm] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._owner_id = owner_id
        self.name = name
        self.description = description
        self._terms: list[TaxonomyTerm] = terms if terms is not None else []

    @property
    def owner_id(self) -> uuid.UUID:
        return self._owner_id

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def create(
        cls,
        owner_id: uuid.UUID,
        name: TaxonomyName,
        description: str | None = None,
    ) -> Taxonomy:
        if description is not None and len(description) > MAX_TAXONOMY_DESCRIPTION_LENGTH:
            raise TaxonomyDescriptionTooLongError(
                f"Taxonomy description must not exceed {MAX_TAXONOMY_DESCRIPTION_LENGTH} characters"
            )

        taxonomy_id = uuid.uuid4()
        taxonomy = cls(
            owner_id=owner_id,
            name=name,
            description=description,
            id=taxonomy_id,
            created_by=owner_id,
            version=1,
        )
        taxonomy._register_event(
            TaxonomyCreated(
                aggregate_id=taxonomy.id,
                owner_id=owner_id,
                name=name.value,
            )
        )
        return taxonomy

    # -- Taxonomy updates ------------------------------------------------------

    def rename(self, new_name: TaxonomyName) -> None:
        if self.is_deleted():
            raise TaxonomyNotActiveError()
        old_name = self.name.value
        self.name = new_name
        self._touch()
        self._register_event(
            TaxonomyRenamed(
                aggregate_id=self.id,
                old_name=old_name,
                new_name=new_name.value,
            )
        )

    def update_description(self, description: str | None) -> None:
        if self.is_deleted():
            raise TaxonomyNotActiveError()
        if description is not None and len(description) > MAX_TAXONOMY_DESCRIPTION_LENGTH:
            raise TaxonomyDescriptionTooLongError(
                f"Taxonomy description must not exceed {MAX_TAXONOMY_DESCRIPTION_LENGTH} characters"
            )
        self.description = description
        self._touch()
        self._register_event(TaxonomyDescriptionUpdated(aggregate_id=self.id))

    # -- Lifecycle overrides ---------------------------------------------------

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        # Count active terms before cascade
        cascaded_count = sum(1 for t in self._terms if t.is_active())
        # Cascade soft-delete to all active terms
        for term in self._terms:
            if term.is_active():
                term.soft_delete(deleted_by=deleted_by, retention=retention)
        super().soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
        self._touch()
        self._register_event(
            TaxonomySoftDeleted(
                aggregate_id=self.id,
                deleted_by=deleted_by,
                term_count=cascaded_count,
            )
        )

    def recover(self) -> None:
        super().recover()
        self._touch()
        self._register_event(TaxonomyRecovered(aggregate_id=self.id))

    # -- Term operations -------------------------------------------------------

    def add_term(
        self,
        name: TermName,
        parent_term_id: uuid.UUID | None = None,
        description: str | None = None,
    ) -> TaxonomyTerm:
        if self.is_deleted():
            raise TaxonomyNotActiveError()
        if self.active_term_count >= MAX_TERMS_PER_TAXONOMY:
            raise MaxTermsExceededError()
        if self._name_exists(name):
            raise TermNameAlreadyExistsError()
        if description is not None and len(description) > MAX_TERM_DESCRIPTION_LENGTH:
            raise TermDescriptionTooLongError(
                f"Term description must not exceed {MAX_TERM_DESCRIPTION_LENGTH} characters"
            )
        if parent_term_id is not None:
            parent = self._find_term_by_id(parent_term_id)
            if parent is None:
                raise ParentTermNotFoundError()
            if parent.is_deleted():
                raise ParentTermDeletedError()

        term = TaxonomyTerm(
            id=uuid.uuid4(),
            taxonomy_id=self.id,
            name=name,
            description=description,
            parent_term_id=parent_term_id,
            sort_order=self._next_sort_order(parent_term_id),
        )
        self._terms.append(term)
        self._touch()
        self._register_event(
            TermAdded(
                aggregate_id=self.id,
                term_id=term.id,
                name=name.value,
                parent_term_id=parent_term_id,
            )
        )
        return term

    def rename_term(self, term_id: uuid.UUID, new_name: TermName) -> None:
        term = self._get_active_term(term_id)
        if self._name_exists(new_name, exclude_term_id=term_id):
            raise TermNameAlreadyExistsError()
        old_name = term.name.value
        term._rename(new_name)
        self._touch()
        self._register_event(
            TermRenamed(
                aggregate_id=self.id,
                term_id=term_id,
                old_name=old_name,
                new_name=new_name.value,
            )
        )

    def update_term_description(self, term_id: uuid.UUID, description: str | None) -> None:
        term = self._get_active_term(term_id)
        if description is not None and len(description) > MAX_TERM_DESCRIPTION_LENGTH:
            raise TermDescriptionTooLongError(
                f"Term description must not exceed {MAX_TERM_DESCRIPTION_LENGTH} characters"
            )
        term._update_description(description)
        self._touch()
        self._register_event(TermDescriptionUpdated(aggregate_id=self.id, term_id=term_id))

    def move_term(self, term_id: uuid.UUID, new_parent_id: uuid.UUID | None) -> None:
        term = self._get_active_term(term_id)
        if new_parent_id is not None:
            if new_parent_id == term_id:
                raise CannotBeOwnParentError()
            parent = self._find_term_by_id(new_parent_id)
            if parent is None or parent.is_deleted():
                raise ParentTermNotFoundError()
            if self._would_create_cycle(term_id, new_parent_id):
                raise CircularReferenceError()
        # No-op if same parent
        if term.parent_term_id == new_parent_id:
            return
        old_parent_id = term.parent_term_id
        term._move(new_parent_id)
        term._set_sort_order(self._next_sort_order(new_parent_id, exclude_term_id=term_id))
        self._touch()
        self._register_event(
            TermMoved(
                aggregate_id=self.id,
                term_id=term_id,
                old_parent_id=old_parent_id,
                new_parent_id=new_parent_id,
            )
        )

    def delete_term(self, term_id: uuid.UUID, deleted_by: uuid.UUID) -> None:
        term = self._find_term_by_id(term_id)
        if term is None:
            raise TermNotFoundError()
        if term.is_deleted():
            from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError

            raise AlreadyDeletedError("Term is already deleted")
        # Get retention for cascade
        from emerald.shared_kernel.domain.models.value_objects.retention_period import (
            RetentionUnit,
        )

        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        # Cascade to descendants
        descendants = self._get_all_descendants(term_id)
        descendants_deleted = 0
        for desc in descendants:
            if desc.is_active():
                desc.soft_delete(deleted_by=deleted_by, retention=retention)
                descendants_deleted += 1
        # Delete the term itself
        term.soft_delete(deleted_by=deleted_by, retention=retention)
        self._touch()
        self._register_event(
            TermDeleted(
                aggregate_id=self.id,
                term_id=term_id,
                deleted_by=deleted_by,
                descendants_deleted=descendants_deleted,
            )
        )

    def recover_term(self, term_id: uuid.UUID) -> None:
        term = self._find_term_by_id(term_id)
        if term is None:
            raise TermNotFoundError()
        if term.is_active():
            from emerald.shared_kernel.domain.exceptions import NotDeletedError

            raise NotDeletedError("Term is not deleted")
        if self.is_deleted():
            raise TaxonomyNotActiveError()
        # Check parent is active
        if term.parent_term_id is not None:
            parent = self._find_term_by_id(term.parent_term_id)
            if parent is None or parent.is_deleted():
                raise ParentTermDeletedError()
        term.recover()
        self._touch()
        self._register_event(TermRecovered(aggregate_id=self.id, term_id=term_id))

    def reorder_terms(self, term_ids: list[uuid.UUID], parent_id: uuid.UUID | None = None) -> None:
        # Check for duplicates
        if len(term_ids) != len(set(term_ids)):
            raise IncompleteReorderError()
        # Get all active siblings under parent_id
        active_siblings = [
            t for t in self._terms if t.is_active() and t.parent_term_id == parent_id
        ]
        active_sibling_ids = {t.id for t in active_siblings}
        provided_ids = set(term_ids)
        # All provided IDs must exist and be active siblings of parent_id
        for tid in term_ids:
            if tid not in active_sibling_ids:
                raise TermNotFoundError()
        # Must be complete set
        if provided_ids != active_sibling_ids:
            raise IncompleteReorderError()
        # Apply new sort order
        id_to_term = {t.id: t for t in active_siblings}
        for order, tid in enumerate(term_ids):
            id_to_term[tid]._set_sort_order(order)
        self._touch()
        self._register_event(
            TermsReordered(
                aggregate_id=self.id,
                parent_id=parent_id,
                ordered_term_ids=tuple(term_ids),
            )
        )

    # -- Query methods ---------------------------------------------------------

    def find_term(self, term_id: uuid.UUID) -> TaxonomyTerm | None:
        return self._find_term_by_id(term_id)

    def get_term(self, term_id: uuid.UUID) -> TaxonomyTerm:
        term = self._find_term_by_id(term_id)
        if term is None:
            raise TermNotFoundError()
        return term

    def get_root_terms(self) -> list[TaxonomyTerm]:
        return sorted(
            [t for t in self._terms if t.is_active() and t.parent_term_id is None],
            key=lambda t: t.sort_order,
        )

    def get_children(self, term_id: uuid.UUID) -> list[TaxonomyTerm]:
        return sorted(
            [t for t in self._terms if t.is_active() and t.parent_term_id == term_id],
            key=lambda t: t.sort_order,
        )

    def get_descendants(self, term_id: uuid.UUID) -> list[TaxonomyTerm]:
        result: list[TaxonomyTerm] = []
        self._collect_active_descendants(term_id, result)
        return result

    def get_term_path(self, term_id: uuid.UUID) -> TaxonomyPath:
        term = self._find_term_by_id(term_id)
        if term is None:
            raise TermNotFoundError()
        segments: list[str] = []
        current: TaxonomyTerm | None = term
        while current is not None:
            segments.append(current.name.value)
            if current.parent_term_id is not None:
                current = self._find_term_by_id(current.parent_term_id)
            else:
                current = None
        segments.reverse()
        return TaxonomyPath(segments=tuple(segments))

    def get_term_depth(self, term_id: uuid.UUID) -> int:
        term = self._find_term_by_id(term_id)
        if term is None:
            raise TermNotFoundError()
        depth = 0
        current = term
        while current.parent_term_id is not None:
            parent = self._find_term_by_id(current.parent_term_id)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth

    @property
    def active_term_count(self) -> int:
        return sum(1 for t in self._terms if t.is_active())

    @property
    def terms(self) -> list[TaxonomyTerm]:
        return list(self._terms)

    # -- Cycle detection -------------------------------------------------------

    def _would_create_cycle(self, term_id: uuid.UUID, new_parent_id: uuid.UUID | None) -> bool:
        if new_parent_id is None:
            return False
        current: uuid.UUID | None = new_parent_id
        while current is not None:
            if current == term_id:
                return True
            parent_term = self._find_term_by_id(current)
            current = parent_term.parent_term_id if parent_term is not None else None
        return False

    # -- Private helpers -------------------------------------------------------

    def _find_term_by_id(self, term_id: uuid.UUID) -> TaxonomyTerm | None:
        for term in self._terms:
            if term.id == term_id:
                return term
        return None

    def _get_active_term(self, term_id: uuid.UUID) -> TaxonomyTerm:
        term = self._find_term_by_id(term_id)
        if term is None or term.is_deleted():
            raise TermNotFoundError()
        return term

    def _name_exists(self, name: TermName, exclude_term_id: uuid.UUID | None = None) -> bool:
        for term in self._terms:
            if term.is_deleted():
                continue
            if exclude_term_id is not None and term.id == exclude_term_id:
                continue
            if term.name == name:
                return True
        return False

    def _next_sort_order(
        self, parent_id: uuid.UUID | None, exclude_term_id: uuid.UUID | None = None
    ) -> int:
        siblings = [
            t
            for t in self._terms
            if t.is_active()
            and t.parent_term_id == parent_id
            and (exclude_term_id is None or t.id != exclude_term_id)
        ]
        if not siblings:
            return 0
        return max(t.sort_order for t in siblings) + 1

    def _get_all_descendants(self, term_id: uuid.UUID) -> list[TaxonomyTerm]:
        result: list[TaxonomyTerm] = []
        self._collect_all_descendants(term_id, result)
        return result

    def _collect_all_descendants(self, term_id: uuid.UUID, result: list[TaxonomyTerm]) -> None:
        for term in self._terms:
            if term.parent_term_id == term_id:
                result.append(term)
                self._collect_all_descendants(term.id, result)

    def _collect_active_descendants(self, term_id: uuid.UUID, result: list[TaxonomyTerm]) -> None:
        children = sorted(
            [t for t in self._terms if t.is_active() and t.parent_term_id == term_id],
            key=lambda t: t.sort_order,
        )
        for child in children:
            result.append(child)
            self._collect_active_descendants(child.id, result)

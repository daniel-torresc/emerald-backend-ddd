import uuid
from dataclasses import dataclass

from emerald.classification.domain.events.base import TaxonomyEvent


@dataclass(frozen=True)
class TaxonomyCreated(TaxonomyEvent):
    """Emitted when a new taxonomy is created."""

    owner_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class TaxonomyRenamed(TaxonomyEvent):
    """Emitted when a taxonomy is renamed."""

    old_name: str
    new_name: str


@dataclass(frozen=True)
class TaxonomyDescriptionUpdated(TaxonomyEvent):
    """Emitted when a taxonomy description is updated."""


@dataclass(frozen=True)
class TaxonomySoftDeleted(TaxonomyEvent):
    """Emitted when a taxonomy is soft-deleted."""

    deleted_by: uuid.UUID
    term_count: int


@dataclass(frozen=True)
class TaxonomyRecovered(TaxonomyEvent):
    """Emitted when a soft-deleted taxonomy is recovered."""


@dataclass(frozen=True)
class TermAdded(TaxonomyEvent):
    """Emitted when a term is added to a taxonomy."""

    term_id: uuid.UUID
    name: str
    parent_term_id: uuid.UUID | None = None


@dataclass(frozen=True)
class TermRenamed(TaxonomyEvent):
    """Emitted when a term is renamed."""

    term_id: uuid.UUID
    old_name: str
    new_name: str


@dataclass(frozen=True)
class TermDescriptionUpdated(TaxonomyEvent):
    """Emitted when a term description is updated."""

    term_id: uuid.UUID


@dataclass(frozen=True)
class TermMoved(TaxonomyEvent):
    """Emitted when a term is moved to a new parent."""

    term_id: uuid.UUID
    old_parent_id: uuid.UUID | None = None
    new_parent_id: uuid.UUID | None = None


@dataclass(frozen=True)
class TermDeleted(TaxonomyEvent):
    """Emitted when a term is soft-deleted."""

    term_id: uuid.UUID
    deleted_by: uuid.UUID
    descendants_deleted: int


@dataclass(frozen=True)
class TermRecovered(TaxonomyEvent):
    """Emitted when a soft-deleted term is recovered."""

    term_id: uuid.UUID


@dataclass(frozen=True)
class TermsReordered(TaxonomyEvent):
    """Emitted when terms are reordered."""

    ordered_term_ids: tuple[uuid.UUID, ...]
    parent_id: uuid.UUID | None = None

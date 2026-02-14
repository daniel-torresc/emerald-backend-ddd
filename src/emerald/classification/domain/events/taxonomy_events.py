import uuid
from dataclasses import dataclass, field
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class TaxonomyCreated(DomainEvent):
    """Emitted when a new taxonomy is created."""

    owner_id: uuid.UUID = uuid.UUID(int=0)
    name: str = ""
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TaxonomyRenamed(DomainEvent):
    """Emitted when a taxonomy is renamed."""

    old_name: str = ""
    new_name: str = ""
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TaxonomyDescriptionUpdated(DomainEvent):
    """Emitted when a taxonomy description is updated."""

    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TaxonomySoftDeleted(DomainEvent):
    """Emitted when a taxonomy is soft-deleted."""

    deleted_by: uuid.UUID = uuid.UUID(int=0)
    term_count: int = 0
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TaxonomyRecovered(DomainEvent):
    """Emitted when a soft-deleted taxonomy is recovered."""

    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermAdded(DomainEvent):
    """Emitted when a term is added to a taxonomy."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    name: str = ""
    parent_term_id: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermRenamed(DomainEvent):
    """Emitted when a term is renamed."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    old_name: str = ""
    new_name: str = ""
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermDescriptionUpdated(DomainEvent):
    """Emitted when a term description is updated."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermMoved(DomainEvent):
    """Emitted when a term is moved to a new parent."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    old_parent_id: uuid.UUID | None = None
    new_parent_id: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermDeleted(DomainEvent):
    """Emitted when a term is soft-deleted."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    deleted_by: uuid.UUID = uuid.UUID(int=0)
    descendants_deleted: int = 0
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermRecovered(DomainEvent):
    """Emitted when a soft-deleted term is recovered."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "Taxonomy"


@dataclass(frozen=True)
class TermsReordered(DomainEvent):
    """Emitted when terms are reordered."""

    parent_id: uuid.UUID | None = None
    ordered_term_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)
    aggregate_type: ClassVar[str] = "Taxonomy"

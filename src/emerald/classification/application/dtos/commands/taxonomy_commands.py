import uuid
from dataclasses import dataclass, field

from emerald.shared_kernel.application.dtos.commands import Command

# -- Taxonomy commands ---------------------------------------------------------


@dataclass(frozen=True)
class CreateTaxonomy(Command):
    """Command to create a new taxonomy."""

    owner_id: uuid.UUID = uuid.UUID(int=0)
    name: str = ""
    description: str | None = None


@dataclass(frozen=True)
class RenameTaxonomy(Command):
    """Command to rename a taxonomy."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    new_name: str = ""


@dataclass(frozen=True)
class UpdateTaxonomyDescription(Command):
    """Command to update a taxonomy's description."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    description: str | None = None


@dataclass(frozen=True)
class SoftDeleteTaxonomy(Command):
    """Command to soft-delete a taxonomy."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class RecoverTaxonomy(Command):
    """Command to recover a soft-deleted taxonomy."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)


# -- Term commands -------------------------------------------------------------


@dataclass(frozen=True)
class AddTerm(Command):
    """Command to add a term to a taxonomy."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    name: str = ""
    parent_term_id: uuid.UUID | None = None
    description: str | None = None


@dataclass(frozen=True)
class RenameTerm(Command):
    """Command to rename a term."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)
    new_name: str = ""


@dataclass(frozen=True)
class UpdateTermDescription(Command):
    """Command to update a term's description."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)
    description: str | None = None


@dataclass(frozen=True)
class MoveTerm(Command):
    """Command to move a term to a new parent."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)
    new_parent_id: uuid.UUID | None = None


@dataclass(frozen=True)
class DeleteTerm(Command):
    """Command to soft-delete a term."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class RecoverTerm(Command):
    """Command to recover a soft-deleted term."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class ReorderTerms(Command):
    """Command to reorder sibling terms."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    owner_id: uuid.UUID = uuid.UUID(int=0)
    term_ids: list[uuid.UUID] = field(default_factory=list)
    parent_id: uuid.UUID | None = None

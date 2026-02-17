import uuid
from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class AssignTerm(Command):
    """Assign a term to a transaction (handles reassignment transparently)."""

    transaction_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)
    user_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class RemoveAssignment(Command):
    """Remove the term assignment for a taxonomy from a transaction."""

    transaction_id: uuid.UUID = uuid.UUID(int=0)
    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    user_id: uuid.UUID = uuid.UUID(int=0)

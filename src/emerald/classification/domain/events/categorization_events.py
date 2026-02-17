import uuid
from dataclasses import dataclass
from typing import ClassVar

from emerald.classification.domain.models.value_objects.uncategorization_reason import (
    UncategorizationReason,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class TransactionCategorized(DomainEvent):
    """Emitted when a term is assigned to a transaction."""

    term_id: uuid.UUID = uuid.UUID(int=0)
    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    assignment_id: uuid.UUID = uuid.UUID(int=0)
    assigned_by: uuid.UUID = uuid.UUID(int=0)
    is_reassignment: bool = False
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionUncategorized(DomainEvent):
    """Emitted when a term assignment is removed from a transaction."""

    taxonomy_id: uuid.UUID = uuid.UUID(int=0)
    term_id: uuid.UUID = uuid.UUID(int=0)
    reason: UncategorizationReason = UncategorizationReason.MANUAL
    aggregate_type: ClassVar[str] = "transaction"

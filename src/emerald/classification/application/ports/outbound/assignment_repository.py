import uuid
from typing import Protocol

from emerald.classification.domain.models.entities.transaction_term_assignment import (
    TransactionTermAssignment,
)


class TransactionTermAssignmentRepository(Protocol):
    """Repository for TransactionTermAssignment entities."""

    def save(self, assignment: TransactionTermAssignment) -> None:
        """Persist a new assignment."""
        ...

    def delete(self, assignment_id: uuid.UUID) -> None:
        """Hard delete a single assignment by ID."""
        ...

    def delete_by_term(self, term_id: uuid.UUID) -> list[TransactionTermAssignment]:
        """Remove all assignments for a specific term.

        Returns the deleted assignments (for event emission).
        """
        ...

    def delete_by_taxonomy(self, taxonomy_id: uuid.UUID) -> list[TransactionTermAssignment]:
        """Remove all assignments for an entire taxonomy.

        Returns the deleted assignments (for event emission).
        """
        ...

    def delete_by_transaction(self, transaction_id: uuid.UUID) -> list[TransactionTermAssignment]:
        """Remove all assignments for a specific transaction.

        Returns the deleted assignments (for event emission).
        """
        ...

    def find_by_transaction(self, transaction_id: uuid.UUID) -> list[TransactionTermAssignment]:
        """All assignments for a transaction (one per taxonomy)."""
        ...

    def find_by_transaction_and_taxonomy(
        self, transaction_id: uuid.UUID, taxonomy_id: uuid.UUID
    ) -> TransactionTermAssignment | None:
        """Assignment for a specific transaction + taxonomy pair."""
        ...

    def find_by_term(self, term_id: uuid.UUID) -> list[TransactionTermAssignment]:
        """All assignments referencing a specific term."""
        ...

    def find_transaction_ids_by_term(self, term_id: uuid.UUID) -> list[uuid.UUID]:
        """Transaction IDs with a specific term assigned."""
        ...

    def find_uncategorized_transaction_ids(
        self, account_id: uuid.UUID, taxonomy_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Transaction IDs in the account WITHOUT an assignment in the given taxonomy."""
        ...

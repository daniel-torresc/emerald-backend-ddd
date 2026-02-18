import uuid

from emerald.classification.application.dtos.commands.categorization_commands import (
    AssignTerm,
    RemoveAssignment,
)
from emerald.classification.application.ports.outbound.transaction_access_port import (
    TransactionAccessPort,
)
from emerald.classification.application.ports.outbound.unit_of_work import (
    AbstractClassificationUnitOfWork,
)
from emerald.classification.domain.exceptions.categorization_exceptions import (
    AssignmentNotFoundError,
)
from emerald.classification.domain.exceptions.taxonomy_exceptions import (
    TaxonomyNotFoundError,
    TermNotFoundError,
)
from emerald.classification.domain.models.entities.transaction_term_assignment import (
    TransactionTermAssignment,
)


class TransactionCategorizationService:
    """Application service for transaction categorization.

    Also implements the CategorizationEventHandler protocol (structural subtyping).
    """

    def __init__(
        self,
        uow: AbstractClassificationUnitOfWork,
        transaction_access_port: TransactionAccessPort,
    ) -> None:
        self._uow = uow
        self._transaction_access_port = transaction_access_port

    # -- Categorization operations ---------------------------------------------

    async def assign_term(self, cmd: AssignTerm) -> TransactionTermAssignment:
        """Assign a term to a transaction. Handles reassignment transparently."""
        async with self._uow:
            # 1. Verify transaction is active
            account_id = self._transaction_access_port.verify_transaction_active(cmd.transaction_id)

            # 2. Verify user has EDITOR permission
            self._transaction_access_port.verify_editor_permission(account_id, cmd.user_id)

            # 3. Load taxonomy containing the term
            taxonomy = self._uow.taxonomies.find_by_term_id(cmd.term_id)
            if taxonomy is None:
                raise TaxonomyNotFoundError()

            # 4. Verify term exists and is active within taxonomy
            term = taxonomy.find_term(cmd.term_id)
            if term is None or term.is_deleted():
                raise TermNotFoundError()

            # 5. Check for existing assignment (reassignment)
            existing = self._uow.assignments.find_by_transaction_and_taxonomy(
                cmd.transaction_id, taxonomy.id
            )
            if existing is not None:
                self._uow.assignments.delete(existing.id)

            # 6-7. Create and persist new assignment
            assignment = TransactionTermAssignment.create(
                transaction_id=cmd.transaction_id,
                term_id=cmd.term_id,
                taxonomy_id=taxonomy.id,
                assigned_by=cmd.user_id,
            )
            self._uow.assignments.save(assignment)

            await self._uow.commit()
            return assignment

    async def remove_assignment(self, cmd: RemoveAssignment) -> None:
        """Remove a term assignment from a transaction by taxonomy."""
        async with self._uow:
            # 1. Verify transaction is active
            account_id = self._transaction_access_port.verify_transaction_active(cmd.transaction_id)

            # 2. Verify user has EDITOR permission
            self._transaction_access_port.verify_editor_permission(account_id, cmd.user_id)

            # 3. Find assignment
            assignment = self._uow.assignments.find_by_transaction_and_taxonomy(
                cmd.transaction_id, cmd.taxonomy_id
            )
            if assignment is None:
                raise AssignmentNotFoundError()

            # 4. Hard delete
            self._uow.assignments.delete(assignment.id)

            await self._uow.commit()

    # -- Query methods ---------------------------------------------------------

    async def get_assignments(self, transaction_id: uuid.UUID) -> list[TransactionTermAssignment]:
        """Return all active assignments for a transaction."""
        async with self._uow:
            return self._uow.assignments.find_by_transaction(transaction_id)

    async def get_assignment_for_taxonomy(
        self, transaction_id: uuid.UUID, taxonomy_id: uuid.UUID
    ) -> TransactionTermAssignment | None:
        """Return assignment for a specific transaction + taxonomy, or None."""
        async with self._uow:
            return self._uow.assignments.find_by_transaction_and_taxonomy(
                transaction_id, taxonomy_id
            )

    async def get_transactions_by_term(
        self, term_id: uuid.UUID, include_descendants: bool = False
    ) -> list[uuid.UUID]:
        """Return transaction IDs with the given term (and optionally descendants)."""
        async with self._uow:
            if not include_descendants:
                return self._uow.assignments.find_transaction_ids_by_term(term_id)

            # Load taxonomy to get descendant term IDs
            taxonomy = self._uow.taxonomies.find_by_term_id(term_id)
            if taxonomy is None:
                return []

            descendants = taxonomy.get_descendants(term_id)
            all_term_ids = [term_id, *[d.id for d in descendants]]

            # Collect transaction IDs for all terms (deduplicating)
            seen: set[uuid.UUID] = set()
            result: list[uuid.UUID] = []
            for tid in all_term_ids:
                for tx_id in self._uow.assignments.find_transaction_ids_by_term(tid):
                    if tx_id not in seen:
                        seen.add(tx_id)
                        result.append(tx_id)
            return result

    async def get_uncategorized_transactions(
        self, account_id: uuid.UUID, taxonomy_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Return transaction IDs in the account without an assignment in the taxonomy."""
        async with self._uow:
            return self._uow.assignments.find_uncategorized_transaction_ids(account_id, taxonomy_id)

    # -- CategorizationEventHandler protocol implementation --------------------

    async def handle_term_deleted(self, term_id: uuid.UUID) -> int:
        """Remove all assignments for the deleted term."""
        async with self._uow:
            deleted = self._uow.assignments.delete_by_term(term_id)
            await self._uow.commit()
        return len(deleted)

    async def handle_taxonomy_soft_deleted(self, taxonomy_id: uuid.UUID) -> int:
        """Remove all assignments for the deleted taxonomy."""
        async with self._uow:
            deleted = self._uow.assignments.delete_by_taxonomy(taxonomy_id)
            await self._uow.commit()
        return len(deleted)

    async def handle_transaction_soft_deleted(self, transaction_id: uuid.UUID) -> int:
        """Remove all assignments for the deleted transaction."""
        async with self._uow:
            deleted = self._uow.assignments.delete_by_transaction(transaction_id)
            await self._uow.commit()
        return len(deleted)

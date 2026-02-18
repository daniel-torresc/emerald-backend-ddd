from __future__ import annotations

import uuid

from emerald.classification.application.ports.outbound.unit_of_work import (
    AbstractClassificationUnitOfWork,
)
from emerald.classification.domain.exceptions.categorization_exceptions import (
    TransactionNotActiveError,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.entities.transaction_term_assignment import (
    TransactionTermAssignment,
)
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.shared_kernel.domain.exceptions import AuthorizationError


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

    def find_by_term_id(self, term_id: uuid.UUID) -> Taxonomy | None:
        for taxonomy in self._taxonomies.values():
            if taxonomy.is_deleted():
                continue
            if taxonomy.find_term(term_id) is not None:
                return taxonomy
        return None


class FakeTransactionAccessPort:
    """In-memory transaction access port for tests.

    Configure active transactions and permissions before use.
    """

    def __init__(self) -> None:
        # Maps transaction_id -> account_id for active transactions
        self._active_transactions: dict[uuid.UUID, uuid.UUID] = {}
        # Set of (account_id, user_id) pairs with editor permission
        self._editor_permissions: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def add_active_transaction(self, transaction_id: uuid.UUID, account_id: uuid.UUID) -> None:
        self._active_transactions[transaction_id] = account_id

    def grant_editor_permission(self, account_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self._editor_permissions.add((account_id, user_id))

    def verify_transaction_active(self, transaction_id: uuid.UUID) -> uuid.UUID:
        account_id = self._active_transactions.get(transaction_id)
        if account_id is None:
            raise TransactionNotActiveError()
        return account_id

    def verify_editor_permission(self, account_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if (account_id, user_id) not in self._editor_permissions:
            raise AuthorizationError("Insufficient permission for categorization")


class FakeTransactionTermAssignmentRepository:
    """In-memory assignment repository for tests."""

    def __init__(self) -> None:
        self._assignments: dict[uuid.UUID, TransactionTermAssignment] = {}

    def save(self, assignment: TransactionTermAssignment) -> None:
        self._assignments[assignment.id] = assignment

    def delete(self, assignment_id: uuid.UUID) -> None:
        self._assignments.pop(assignment_id, None)

    def delete_by_term(self, term_id: uuid.UUID) -> list[TransactionTermAssignment]:
        to_delete = [a for a in self._assignments.values() if a.term_id == term_id]
        for a in to_delete:
            del self._assignments[a.id]
        return to_delete

    def delete_by_taxonomy(self, taxonomy_id: uuid.UUID) -> list[TransactionTermAssignment]:
        to_delete = [a for a in self._assignments.values() if a.taxonomy_id == taxonomy_id]
        for a in to_delete:
            del self._assignments[a.id]
        return to_delete

    def delete_by_transaction(self, transaction_id: uuid.UUID) -> list[TransactionTermAssignment]:
        to_delete = [a for a in self._assignments.values() if a.transaction_id == transaction_id]
        for a in to_delete:
            del self._assignments[a.id]
        return to_delete

    def find_by_transaction(self, transaction_id: uuid.UUID) -> list[TransactionTermAssignment]:
        return [a for a in self._assignments.values() if a.transaction_id == transaction_id]

    def find_by_transaction_and_taxonomy(
        self, transaction_id: uuid.UUID, taxonomy_id: uuid.UUID
    ) -> TransactionTermAssignment | None:
        for a in self._assignments.values():
            if a.transaction_id == transaction_id and a.taxonomy_id == taxonomy_id:
                return a
        return None

    def find_by_term(self, term_id: uuid.UUID) -> list[TransactionTermAssignment]:
        return [a for a in self._assignments.values() if a.term_id == term_id]

    def find_transaction_ids_by_term(self, term_id: uuid.UUID) -> list[uuid.UUID]:
        return [a.transaction_id for a in self._assignments.values() if a.term_id == term_id]

    def find_uncategorized_transaction_ids(
        self, account_id: uuid.UUID, taxonomy_id: uuid.UUID
    ) -> list[uuid.UUID]:
        # In a real implementation this would query transactions from Core Finance.
        # For tests, we return an empty list — tests that need this can configure it.
        return []


class FakeClassificationUnitOfWork(AbstractClassificationUnitOfWork):
    """In-memory Unit of Work for Classification tests."""

    taxonomies: FakeTaxonomyRepository
    assignments: FakeTransactionTermAssignmentRepository

    def __init__(self) -> None:
        self.taxonomies = FakeTaxonomyRepository()
        self.assignments = FakeTransactionTermAssignmentRepository()
        self.committed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

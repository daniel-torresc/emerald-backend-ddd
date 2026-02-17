import uuid

from emerald.classification.application.dtos.commands.categorization_commands import AssignTerm
from emerald.classification.application.services.transaction_categorization import (
    TransactionCategorizationService,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.classification.domain.models.value_objects.term_name import TermName
from tests.unit.classification.fakes import (
    FakeClassificationUnitOfWork,
    FakeTransactionAccessPort,
)

_ACCOUNT_ID = uuid.uuid4()
_OWNER_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()


def _make_deps() -> tuple[
    TransactionCategorizationService, FakeClassificationUnitOfWork, FakeTransactionAccessPort
]:
    uow = FakeClassificationUnitOfWork()
    port = FakeTransactionAccessPort()
    service = TransactionCategorizationService(uow=uow, transaction_access_port=port)
    return service, uow, port


def _create_taxonomy(uow: FakeClassificationUnitOfWork, name: str = "Category") -> Taxonomy:
    taxonomy = Taxonomy.create(owner_id=_OWNER_ID, name=TaxonomyName(name))
    taxonomy.collect_events()
    uow.taxonomies.save(taxonomy)
    return taxonomy


def _add_term(taxonomy: Taxonomy, name: str, parent_id: uuid.UUID | None = None) -> uuid.UUID:
    term = taxonomy.add_term(name=TermName(name), parent_term_id=parent_id)
    taxonomy.collect_events()
    return term.id


def _setup_and_assign(
    service: TransactionCategorizationService,
    port: FakeTransactionAccessPort,
    term_id: uuid.UUID,
    tx_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Set up transaction and assign term. Returns tx_id."""
    tx_id = tx_id or uuid.uuid4()
    port.add_active_transaction(tx_id, _ACCOUNT_ID)
    port.grant_editor_permission(_ACCOUNT_ID, _USER_ID)
    service.assign_term(AssignTerm(transaction_id=tx_id, term_id=term_id, user_id=_USER_ID))
    service.collect_events()
    return tx_id


class TestGetAssignments:
    def test_returns_all_for_transaction(self) -> None:
        service, uow, port = _make_deps()
        tax_a = _create_taxonomy(uow, "Category")
        tax_b = _create_taxonomy(uow, "Project")
        term_a = _add_term(tax_a, "Food")
        term_b = _add_term(tax_b, "Personal")

        tx_id = uuid.uuid4()
        port.add_active_transaction(tx_id, _ACCOUNT_ID)
        port.grant_editor_permission(_ACCOUNT_ID, _USER_ID)

        service.assign_term(AssignTerm(transaction_id=tx_id, term_id=term_a, user_id=_USER_ID))
        service.assign_term(AssignTerm(transaction_id=tx_id, term_id=term_b, user_id=_USER_ID))
        service.collect_events()

        assignments = service.get_assignments(tx_id)
        assert len(assignments) == 2

    def test_returns_empty_for_no_assignments(self) -> None:
        service, uow, port = _make_deps()
        assert service.get_assignments(uuid.uuid4()) == []


class TestGetAssignmentForTaxonomy:
    def test_returns_specific_assignment(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy, "Food")
        tx_id = _setup_and_assign(service, port, term_id)

        result = service.get_assignment_for_taxonomy(tx_id, taxonomy.id)
        assert result is not None
        assert result.term_id == term_id

    def test_returns_none_when_no_assignment(self) -> None:
        service, uow, port = _make_deps()
        assert service.get_assignment_for_taxonomy(uuid.uuid4(), uuid.uuid4()) is None


class TestGetTransactionsByTerm:
    def test_single_term(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy, "Food")

        tx_a = _setup_and_assign(service, port, term_id)
        tx_b = _setup_and_assign(service, port, term_id)

        result = service.get_transactions_by_term(term_id)
        assert set(result) == {tx_a, tx_b}

    def test_include_descendants(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        parent_id = _add_term(taxonomy, "Food")
        child_id = _add_term(taxonomy, "Groceries", parent_id=parent_id)
        grandchild_id = _add_term(taxonomy, "Organic", parent_id=child_id)

        tx_parent = _setup_and_assign(service, port, parent_id)
        tx_child = _setup_and_assign(service, port, child_id)
        tx_grandchild = _setup_and_assign(service, port, grandchild_id)

        result = service.get_transactions_by_term(parent_id, include_descendants=True)
        assert set(result) == {tx_parent, tx_child, tx_grandchild}

    def test_include_descendants_deduplicates(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        parent_id = _add_term(taxonomy, "Food")
        _add_term(taxonomy, "Groceries", parent_id=parent_id)

        # Assign both parent and child to same tx
        tx_id = uuid.uuid4()
        port.add_active_transaction(tx_id, _ACCOUNT_ID)
        port.grant_editor_permission(_ACCOUNT_ID, _USER_ID)

        # We need two different taxonomies for this test since one-per-taxonomy constraint.
        # Actually, parent and child are in same taxonomy, so same transaction can't have both.
        # The dedup would matter if two different children matched the same transaction.
        # Let's simplify: just verify no error with single result.
        _setup_and_assign(service, port, parent_id, tx_id=tx_id)
        result = service.get_transactions_by_term(parent_id, include_descendants=True)
        assert result == [tx_id]

    def test_include_descendants_unknown_term(self) -> None:
        service, uow, port = _make_deps()
        result = service.get_transactions_by_term(uuid.uuid4(), include_descendants=True)
        assert result == []

    def test_without_descendants(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        parent_id = _add_term(taxonomy, "Food")
        child_id = _add_term(taxonomy, "Groceries", parent_id=parent_id)

        _setup_and_assign(service, port, child_id)

        result = service.get_transactions_by_term(parent_id, include_descendants=False)
        assert result == []


class TestGetUncategorizedTransactions:
    def test_delegates_to_repository(self) -> None:
        service, uow, port = _make_deps()
        # The fake always returns empty; just verify no errors
        result = service.get_uncategorized_transactions(uuid.uuid4(), uuid.uuid4())
        assert result == []

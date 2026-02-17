import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.categorization_commands import AssignTerm
from emerald.classification.application.services.transaction_categorization import (
    TransactionCategorizationService,
)
from emerald.classification.domain.exceptions.categorization_exceptions import (
    TransactionNotActiveError,
)
from emerald.classification.domain.exceptions.taxonomy_exceptions import (
    TaxonomyNotFoundError,
    TermNotFoundError,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.shared_kernel.domain.exceptions import AuthorizationError
from tests.unit.classification.fakes import (
    FakeClassificationUnitOfWork,
    FakeTransactionAccessPort,
)

# -- Helpers -------------------------------------------------------------------

_OWNER_ID = uuid.uuid4()
_ACCOUNT_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()


def _make_deps() -> tuple[
    TransactionCategorizationService, FakeClassificationUnitOfWork, FakeTransactionAccessPort
]:
    uow = FakeClassificationUnitOfWork()
    port = FakeTransactionAccessPort()
    service = TransactionCategorizationService(uow=uow, transaction_access_port=port)
    return service, uow, port


def _create_taxonomy(
    uow: FakeClassificationUnitOfWork, owner_id: uuid.UUID = _OWNER_ID
) -> Taxonomy:
    taxonomy = Taxonomy.create(owner_id=owner_id, name=TaxonomyName("Category"))
    # Drain creation events
    taxonomy.collect_events()
    uow.taxonomies.save(taxonomy)
    return taxonomy


def _add_term(taxonomy: Taxonomy, name: str = "Food") -> uuid.UUID:
    term = taxonomy.add_term(name=TermName(name))
    taxonomy.collect_events()
    return term.id


def _setup_transaction(
    port: FakeTransactionAccessPort,
    transaction_id: uuid.UUID | None = None,
    account_id: uuid.UUID = _ACCOUNT_ID,
    user_id: uuid.UUID = _USER_ID,
) -> uuid.UUID:
    tx_id = transaction_id or uuid.uuid4()
    port.add_active_transaction(tx_id, account_id)
    port.grant_editor_permission(account_id, user_id)
    return tx_id


def _make_cmd(**overrides: Any) -> AssignTerm:
    defaults: dict[str, Any] = {
        "transaction_id": uuid.uuid4(),
        "term_id": uuid.uuid4(),
        "user_id": _USER_ID,
    }
    defaults.update(overrides)
    return AssignTerm(**defaults)


# -- Tests ---------------------------------------------------------------------


class TestAssignTermHappyPath:
    def test_assign_creates_assignment(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy)
        tx_id = _setup_transaction(port)

        cmd = _make_cmd(transaction_id=tx_id, term_id=term_id)
        assignment = service.assign_term(cmd)

        assert assignment.transaction_id == tx_id
        assert assignment.term_id == term_id
        assert assignment.taxonomy_id == taxonomy.id
        assert assignment.assigned_by == _USER_ID

    def test_assign_persists_to_repository(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy)
        tx_id = _setup_transaction(port)

        cmd = _make_cmd(transaction_id=tx_id, term_id=term_id)
        assignment = service.assign_term(cmd)

        found = uow.assignments.find_by_transaction_and_taxonomy(tx_id, taxonomy.id)
        assert found is not None
        assert found.id == assignment.id

    def test_assign_commits_uow(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy)
        tx_id = _setup_transaction(port)

        cmd = _make_cmd(transaction_id=tx_id, term_id=term_id)
        service.assign_term(cmd)

        assert uow.committed is True


class TestAssignTermReassignment:
    def test_reassignment_replaces_old_assignment(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_a_id = _add_term(taxonomy, "Food")
        term_b_id = _add_term(taxonomy, "Transport")
        tx_id = _setup_transaction(port)

        service.assign_term(_make_cmd(transaction_id=tx_id, term_id=term_a_id))

        new_assignment = service.assign_term(_make_cmd(transaction_id=tx_id, term_id=term_b_id))

        # Only one assignment for this transaction + taxonomy
        assignments = uow.assignments.find_by_transaction(tx_id)
        assert len(assignments) == 1
        assert assignments[0].term_id == term_b_id
        assert assignments[0].id == new_assignment.id


class TestAssignTermMultiTaxonomy:
    def test_terms_from_different_taxonomies_coexist(self) -> None:
        service, uow, port = _make_deps()

        tax_a = Taxonomy.create(owner_id=_OWNER_ID, name=TaxonomyName("Category"))
        tax_a.collect_events()
        uow.taxonomies.save(tax_a)

        tax_b = Taxonomy.create(owner_id=_OWNER_ID, name=TaxonomyName("Project"))
        tax_b.collect_events()
        uow.taxonomies.save(tax_b)

        term_a_id = _add_term(tax_a, "Food")
        term_b_id = _add_term(tax_b, "Personal")

        tx_id = _setup_transaction(port)

        service.assign_term(_make_cmd(transaction_id=tx_id, term_id=term_a_id))
        service.assign_term(_make_cmd(transaction_id=tx_id, term_id=term_b_id))

        assignments = uow.assignments.find_by_transaction(tx_id)
        assert len(assignments) == 2
        taxonomy_ids = {a.taxonomy_id for a in assignments}
        assert taxonomy_ids == {tax_a.id, tax_b.id}


class TestAssignTermSplitChildIndependence:
    def test_parent_and_child_categorized_independently(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_food = _add_term(taxonomy, "Food")
        term_transport = _add_term(taxonomy, "Transport")

        parent_tx = _setup_transaction(port)
        child_tx = _setup_transaction(port)

        service.assign_term(_make_cmd(transaction_id=parent_tx, term_id=term_food))
        service.assign_term(_make_cmd(transaction_id=child_tx, term_id=term_transport))

        parent_assignments = uow.assignments.find_by_transaction(parent_tx)
        child_assignments = uow.assignments.find_by_transaction(child_tx)

        assert len(parent_assignments) == 1
        assert parent_assignments[0].term_id == term_food
        assert len(child_assignments) == 1
        assert child_assignments[0].term_id == term_transport


class TestAssignTermErrors:
    def test_transaction_not_active_raises(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy)

        cmd = _make_cmd(term_id=term_id)
        # transaction_id not registered in port
        with pytest.raises(TransactionNotActiveError):
            service.assign_term(cmd)

    def test_no_editor_permission_raises(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy)
        tx_id = uuid.uuid4()
        port.add_active_transaction(tx_id, _ACCOUNT_ID)
        # No editor permission granted

        cmd = _make_cmd(transaction_id=tx_id, term_id=term_id)
        with pytest.raises(AuthorizationError):
            service.assign_term(cmd)

    def test_taxonomy_not_found_raises(self) -> None:
        service, uow, port = _make_deps()
        tx_id = _setup_transaction(port)
        # No taxonomy in UoW

        cmd = _make_cmd(transaction_id=tx_id, term_id=uuid.uuid4())
        with pytest.raises(TaxonomyNotFoundError):
            service.assign_term(cmd)

    def test_term_not_found_raises(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        tx_id = _setup_transaction(port)

        # Use a random term_id that doesn't exist in taxonomy.
        # But find_by_term_id won't find the taxonomy, so TaxonomyNotFoundError.
        # To test TermNotFoundError, we need a term that exists but is deleted.
        term_id = _add_term(taxonomy, "Food")
        # Soft-delete the term
        taxonomy.delete_term(term_id, deleted_by=_OWNER_ID)
        taxonomy.collect_events()

        cmd = _make_cmd(transaction_id=tx_id, term_id=term_id)
        with pytest.raises(TermNotFoundError):
            service.assign_term(cmd)

    def test_taxonomy_soft_deleted_raises(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        _add_term(taxonomy, "Food")
        tx_id = _setup_transaction(port)

        # Soft-delete the taxonomy
        from emerald.shared_kernel.domain.models.value_objects.retention_period import (
            RetentionPeriod,
            RetentionUnit,
        )

        taxonomy.soft_delete(_OWNER_ID, RetentionPeriod(duration=30, unit=RetentionUnit.DAYS))
        taxonomy.collect_events()

        cmd = _make_cmd(transaction_id=tx_id, term_id=uuid.uuid4())
        with pytest.raises(TaxonomyNotFoundError):
            service.assign_term(cmd)

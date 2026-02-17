import uuid

from emerald.classification.application.dtos.commands.categorization_commands import AssignTerm
from emerald.classification.application.services.transaction_categorization import (
    TransactionCategorizationService,
)
from emerald.classification.domain.events.categorization_events import TransactionUncategorized
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.classification.domain.models.value_objects.uncategorization_reason import (
    UncategorizationReason,
)
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


def _add_term(taxonomy: Taxonomy, name: str) -> uuid.UUID:
    term = taxonomy.add_term(name=TermName(name))
    taxonomy.collect_events()
    return term.id


def _assign(
    service: TransactionCategorizationService,
    port: FakeTransactionAccessPort,
    tx_id: uuid.UUID,
    term_id: uuid.UUID,
) -> None:
    port.add_active_transaction(tx_id, _ACCOUNT_ID)
    port.grant_editor_permission(_ACCOUNT_ID, _USER_ID)
    service.assign_term(AssignTerm(transaction_id=tx_id, term_id=term_id, user_id=_USER_ID))
    service.collect_events()


class TestHandleTermDeleted:
    def test_removes_all_assignments_for_term(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy, "Food")

        tx_a, tx_b = uuid.uuid4(), uuid.uuid4()
        _assign(service, port, tx_a, term_id)
        _assign(service, port, tx_b, term_id)

        count = service.handle_term_deleted(term_id)

        assert count == 2
        assert uow.assignments.find_by_term(term_id) == []

    def test_emits_events_with_term_deleted_reason(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy, "Food")

        tx_id = uuid.uuid4()
        _assign(service, port, tx_id, term_id)

        service.handle_term_deleted(term_id)

        events = service.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUncategorized)
        assert event.aggregate_id == tx_id
        assert event.reason == UncategorizationReason.TERM_DELETED

    def test_no_assignments_returns_zero(self) -> None:
        service, uow, port = _make_deps()
        count = service.handle_term_deleted(uuid.uuid4())
        assert count == 0
        assert service.collect_events() == []


class TestHandleTaxonomySoftDeleted:
    def test_removes_all_assignments_for_taxonomy(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_a = _add_term(taxonomy, "Food")
        term_b = _add_term(taxonomy, "Transport")

        tx_a, tx_b = uuid.uuid4(), uuid.uuid4()
        _assign(service, port, tx_a, term_a)
        _assign(service, port, tx_b, term_b)

        count = service.handle_taxonomy_soft_deleted(taxonomy.id)

        assert count == 2
        assert uow.assignments.find_by_transaction(tx_a) == []
        assert uow.assignments.find_by_transaction(tx_b) == []

    def test_emits_events_with_taxonomy_deleted_reason(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy, "Food")

        tx_id = uuid.uuid4()
        _assign(service, port, tx_id, term_id)

        service.handle_taxonomy_soft_deleted(taxonomy.id)

        events = service.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TransactionUncategorized)
        assert events[0].reason == UncategorizationReason.TAXONOMY_DELETED

    def test_no_assignments_returns_zero(self) -> None:
        service, uow, port = _make_deps()
        count = service.handle_taxonomy_soft_deleted(uuid.uuid4())
        assert count == 0


class TestHandleTransactionSoftDeleted:
    def test_removes_all_assignments_for_transaction(self) -> None:
        service, uow, port = _make_deps()
        tax_a = _create_taxonomy(uow, "Category")
        tax_b = _create_taxonomy(uow, "Project")
        term_a = _add_term(tax_a, "Food")
        term_b = _add_term(tax_b, "Personal")

        tx_id = uuid.uuid4()
        _assign(service, port, tx_id, term_a)
        _assign(service, port, tx_id, term_b)

        count = service.handle_transaction_soft_deleted(tx_id)

        assert count == 2
        assert uow.assignments.find_by_transaction(tx_id) == []

    def test_emits_events_with_transaction_deleted_reason(self) -> None:
        service, uow, port = _make_deps()
        taxonomy = _create_taxonomy(uow)
        term_id = _add_term(taxonomy, "Food")

        tx_id = uuid.uuid4()
        _assign(service, port, tx_id, term_id)

        service.handle_transaction_soft_deleted(tx_id)

        events = service.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TransactionUncategorized)
        assert events[0].reason == UncategorizationReason.TRANSACTION_DELETED
        assert events[0].aggregate_id == tx_id

    def test_no_assignments_returns_zero(self) -> None:
        service, uow, port = _make_deps()
        count = service.handle_transaction_soft_deleted(uuid.uuid4())
        assert count == 0

    def test_multiple_assignments_each_get_event(self) -> None:
        service, uow, port = _make_deps()
        tax_a = _create_taxonomy(uow, "Category")
        tax_b = _create_taxonomy(uow, "Project")
        term_a = _add_term(tax_a, "Food")
        term_b = _add_term(tax_b, "Personal")

        tx_id = uuid.uuid4()
        _assign(service, port, tx_id, term_a)
        _assign(service, port, tx_id, term_b)

        service.handle_transaction_soft_deleted(tx_id)

        events = service.collect_events()
        assert len(events) == 2
        for e in events:
            assert isinstance(e, TransactionUncategorized)
            assert e.reason == UncategorizationReason.TRANSACTION_DELETED

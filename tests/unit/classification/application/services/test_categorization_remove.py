import uuid

import pytest

from emerald.classification.application.dtos.commands.categorization_commands import (
    AssignTerm,
    RemoveAssignment,
)
from emerald.classification.application.services.transaction_categorization import (
    TransactionCategorizationService,
)
from emerald.classification.domain.events.categorization_events import TransactionUncategorized
from emerald.classification.domain.exceptions.categorization_exceptions import (
    AssignmentNotFoundError,
    TransactionNotActiveError,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.classification.domain.models.value_objects.uncategorization_reason import (
    UncategorizationReason,
)
from emerald.shared_kernel.domain.exceptions import AuthorizationError
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


def _setup(
    uow: FakeClassificationUnitOfWork,
    port: FakeTransactionAccessPort,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Set up a taxonomy + term + active transaction. Returns (tx_id, term_id, taxonomy_id)."""
    taxonomy = Taxonomy.create(owner_id=_OWNER_ID, name=TaxonomyName("Category"))
    taxonomy.collect_events()
    uow.taxonomies.save(taxonomy)

    term = taxonomy.add_term(name=TermName("Food"))
    taxonomy.collect_events()
    term_id = term.id

    tx_id = uuid.uuid4()
    port.add_active_transaction(tx_id, _ACCOUNT_ID)
    port.grant_editor_permission(_ACCOUNT_ID, _USER_ID)
    return tx_id, term_id, taxonomy.id


class TestRemoveAssignment:
    def test_remove_existing_assignment(self) -> None:
        service, uow, port = _make_deps()
        tx_id, term_id, taxonomy_id = _setup(uow, port)

        # First assign
        service.assign_term(AssignTerm(transaction_id=tx_id, term_id=term_id, user_id=_USER_ID))
        service.collect_events()

        # Then remove
        service.remove_assignment(
            RemoveAssignment(transaction_id=tx_id, taxonomy_id=taxonomy_id, user_id=_USER_ID)
        )

        # Verify deleted
        assert uow.assignments.find_by_transaction(tx_id) == []

    def test_remove_emits_uncategorized_event(self) -> None:
        service, uow, port = _make_deps()
        tx_id, term_id, taxonomy_id = _setup(uow, port)

        service.assign_term(AssignTerm(transaction_id=tx_id, term_id=term_id, user_id=_USER_ID))
        service.collect_events()

        service.remove_assignment(
            RemoveAssignment(transaction_id=tx_id, taxonomy_id=taxonomy_id, user_id=_USER_ID)
        )

        events = service.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionUncategorized)
        assert event.aggregate_id == tx_id
        assert event.taxonomy_id == taxonomy_id
        assert event.term_id == term_id
        assert event.reason == UncategorizationReason.MANUAL

    def test_remove_nonexistent_raises(self) -> None:
        service, uow, port = _make_deps()
        tx_id, _, taxonomy_id = _setup(uow, port)
        # No assignment exists

        with pytest.raises(AssignmentNotFoundError):
            service.remove_assignment(
                RemoveAssignment(transaction_id=tx_id, taxonomy_id=taxonomy_id, user_id=_USER_ID)
            )

    def test_remove_transaction_not_active_raises(self) -> None:
        service, uow, port = _make_deps()
        # No transaction registered
        with pytest.raises(TransactionNotActiveError):
            service.remove_assignment(
                RemoveAssignment(
                    transaction_id=uuid.uuid4(), taxonomy_id=uuid.uuid4(), user_id=_USER_ID
                )
            )

    def test_remove_no_editor_permission_raises(self) -> None:
        service, uow, port = _make_deps()
        tx_id = uuid.uuid4()
        port.add_active_transaction(tx_id, _ACCOUNT_ID)
        # No editor permission granted

        with pytest.raises(AuthorizationError):
            service.remove_assignment(
                RemoveAssignment(transaction_id=tx_id, taxonomy_id=uuid.uuid4(), user_id=_USER_ID)
            )

import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    AddTerm,
    CreateTaxonomy,
    DeleteTerm,
    RecoverTerm,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.events.taxonomy_events import TermDeleted, TermRecovered
from emerald.classification.domain.exceptions import ParentTermDeletedError
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.classification.fakes import FakeClassificationUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_service() -> tuple[TaxonomyManagementService, FakeClassificationUnitOfWork]:
    uow = FakeClassificationUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    service = TaxonomyManagementService(uow=uow, retention_policy_service=retention_service)
    return service, uow


def _make_add_term_cmd(**overrides: Any) -> AddTerm:
    defaults: dict[str, Any] = {
        "taxonomy_id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "name": "Term",
    }
    defaults.update(overrides)
    return AddTerm(**defaults)


class TestDeleteTerm:
    def test_delete_term_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        uow.committed = False

        service.delete_term(DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id))

        assert term.is_deleted()
        assert uow.committed is True

    def test_delete_term_emits_event(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        list(uow.collect_new_events())

        service.delete_term(DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id))

        events = list(uow.collect_new_events())
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TermDeleted)
        assert event.term_id == term.id
        assert event.deleted_by == owner_id

    def test_delete_term_cascade_descendants(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )
        grandchild = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Apples",
                parent_term_id=child.id,
            )
        )
        list(uow.collect_new_events())

        service.delete_term(
            DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=parent.id)
        )

        assert parent.is_deleted()
        assert child.is_deleted()
        assert grandchild.is_deleted()

        events = list(uow.collect_new_events())
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TermDeleted)
        assert event.descendants_deleted == 2


class TestRecoverTerm:
    def test_recover_term_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        service.delete_term(DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id))
        uow.committed = False

        service.recover_term(
            RecoverTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id)
        )

        assert term.is_active()
        assert uow.committed is True

    def test_recover_term_emits_event(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        service.delete_term(DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id))
        list(uow.collect_new_events())

        service.recover_term(
            RecoverTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id)
        )

        events = list(uow.collect_new_events())
        assert len(events) == 1
        assert isinstance(events[0], TermRecovered)
        assert events[0].term_id == term.id

    def test_recover_term_parent_deleted_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )

        # Delete parent (cascades to child)
        service.delete_term(
            DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=parent.id)
        )

        # Try to recover child while parent is still deleted
        with pytest.raises(ParentTermDeletedError):
            service.recover_term(
                RecoverTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=child.id)
            )

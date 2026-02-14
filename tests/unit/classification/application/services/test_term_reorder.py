import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    AddTerm,
    CreateTaxonomy,
    ReorderTerms,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.events.taxonomy_events import TermsReordered
from emerald.classification.domain.exceptions import IncompleteReorderError
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


class TestReorderTerms:
    def test_reorder_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        term_a = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="A")
        )
        term_b = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="B")
        )
        term_c = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="C")
        )
        uow.committed = False

        # Reverse the order: C, B, A
        service.reorder_terms(
            ReorderTerms(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_ids=[term_c.id, term_b.id, term_a.id],
                parent_id=None,
            )
        )

        assert term_c.sort_order == 0
        assert term_b.sort_order == 1
        assert term_a.sort_order == 2
        assert uow.committed is True

    def test_reorder_emits_event(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        term_a = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="A")
        )
        term_b = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="B")
        )
        list(uow.collect_new_events())

        service.reorder_terms(
            ReorderTerms(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_ids=[term_b.id, term_a.id],
                parent_id=None,
            )
        )

        events = list(uow.collect_new_events())
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TermsReordered)
        assert event.parent_id is None
        assert event.ordered_term_ids == (term_b.id, term_a.id)

    def test_reorder_incomplete_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        term_a = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="A")
        )
        service.add_term(_make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="B"))

        # Only include one of two siblings
        with pytest.raises(IncompleteReorderError):
            service.reorder_terms(
                ReorderTerms(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_ids=[term_a.id],
                    parent_id=None,
                )
            )

    def test_reorder_duplicates_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        term_a = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="A")
        )
        service.add_term(_make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="B"))

        # Duplicate IDs in the list
        with pytest.raises(IncompleteReorderError):
            service.reorder_terms(
                ReorderTerms(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_ids=[term_a.id, term_a.id],
                    parent_id=None,
                )
            )

    def test_reorder_children_of_parent(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        child_a = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )
        child_b = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Vegetables",
                parent_term_id=parent.id,
            )
        )

        service.reorder_terms(
            ReorderTerms(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_ids=[child_b.id, child_a.id],
                parent_id=parent.id,
            )
        )

        assert child_b.sort_order == 0
        assert child_a.sort_order == 1

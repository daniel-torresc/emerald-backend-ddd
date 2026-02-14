import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    AddTerm,
    CreateTaxonomy,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.events.taxonomy_events import TermAdded
from emerald.classification.domain.exceptions import (
    TaxonomyNotFoundError,
    TermNameAlreadyExistsError,
)
from emerald.classification.domain.models.entities.taxonomy_term import TaxonomyTerm
from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.classification.fakes import FakeClassificationUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_service() -> tuple[TaxonomyManagementService, FakeClassificationUnitOfWork]:
    uow = FakeClassificationUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    service = TaxonomyManagementService(uow=uow, retention_policy_service=retention_service)
    return service, uow


def _create_taxonomy(
    service: TaxonomyManagementService, owner_id: uuid.UUID, name: str = "My Taxonomy"
) -> uuid.UUID:
    taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name=name))
    return taxonomy.id


def _make_add_term_cmd(**overrides: Any) -> AddTerm:
    defaults: dict[str, Any] = {
        "taxonomy_id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "name": "Food",
    }
    defaults.update(overrides)
    return AddTerm(**defaults)


class TestAddRootTerm:
    def test_add_root_term_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)
        uow.committed = False

        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=owner_id, name="Food")
        )

        assert isinstance(term, TaxonomyTerm)
        assert term.name == TermName("Food")
        assert term.parent_term_id is None
        assert term.taxonomy_id == taxonomy_id
        assert uow.committed is True

    def test_add_root_term_emits_event(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)
        list(uow.collect_new_events())

        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=owner_id, name="Food")
        )

        events = list(uow.collect_new_events())
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TermAdded)
        assert event.term_id == term.id
        assert event.name == "Food"
        assert event.parent_term_id is None


class TestAddChildTerm:
    def test_add_child_with_parent(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)

        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=owner_id, name="Food")
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy_id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )

        assert child.parent_term_id == parent.id
        assert child.name == TermName("Fruits")

    def test_add_child_emits_event_with_parent_id(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)
        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=owner_id, name="Food")
        )
        list(uow.collect_new_events())

        service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy_id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )

        events = list(uow.collect_new_events())
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TermAdded)
        assert event.parent_term_id == parent.id


class TestAddTermWithDescription:
    def test_add_term_with_description(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)

        term = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy_id,
                owner_id=owner_id,
                name="Food",
                description="All food-related expenses",
            )
        )

        assert term.description == "All food-related expenses"


class TestAddTermUniqueness:
    def test_duplicate_name_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)

        service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=owner_id, name="Food")
        )

        with pytest.raises(TermNameAlreadyExistsError):
            service.add_term(
                _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=owner_id, name="Food")
            )


class TestAddTermNotFound:
    def test_taxonomy_not_found_raises(self) -> None:
        service, uow = _make_service()

        with pytest.raises(TaxonomyNotFoundError):
            service.add_term(
                _make_add_term_cmd(taxonomy_id=uuid.uuid4(), owner_id=uuid.uuid4(), name="Food")
            )

    def test_wrong_owner_raises_not_found(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy_id = _create_taxonomy(service, owner_id)

        other_user = uuid.uuid4()
        with pytest.raises(TaxonomyNotFoundError):
            service.add_term(
                _make_add_term_cmd(taxonomy_id=taxonomy_id, owner_id=other_user, name="Food")
            )

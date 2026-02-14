import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    AddTerm,
    CreateTaxonomy,
    RenameTerm,
    UpdateTermDescription,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.constants import MAX_TERM_DESCRIPTION_LENGTH
from emerald.classification.domain.events.taxonomy_events import (
    TermDescriptionUpdated,
    TermRenamed,
)
from emerald.classification.domain.exceptions import (
    TermDescriptionTooLongError,
    TermNameAlreadyExistsError,
)
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


def _make_add_term_cmd(**overrides: Any) -> AddTerm:
    defaults: dict[str, Any] = {
        "taxonomy_id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "name": "Food",
    }
    defaults.update(overrides)
    return AddTerm(**defaults)


class TestRenameTerm:
    def test_rename_term_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        uow.committed = False

        service.rename_term(
            RenameTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=term.id,
                new_name="Groceries",
            )
        )

        assert term.name == TermName("Groceries")
        assert uow.committed is True

    def test_rename_term_emits_event(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        list(uow.collect_new_events())

        service.rename_term(
            RenameTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=term.id,
                new_name="Groceries",
            )
        )

        events = list(uow.collect_new_events())
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TermRenamed)
        assert event.old_name == "Food"
        assert event.new_name == "Groceries"

    def test_rename_term_uniqueness_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        term2 = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Travel")
        )

        with pytest.raises(TermNameAlreadyExistsError):
            service.rename_term(
                RenameTerm(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_id=term2.id,
                    new_name="Food",
                )
            )


class TestUpdateTermDescription:
    def test_update_term_description_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        uow.committed = False

        service.update_term_description(
            UpdateTermDescription(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=term.id,
                description="All food expenses",
            )
        )

        assert term.description == "All food expenses"
        assert uow.committed is True

    def test_update_term_description_emits_event(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        list(uow.collect_new_events())

        service.update_term_description(
            UpdateTermDescription(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=term.id,
                description="Updated",
            )
        )

        events = list(uow.collect_new_events())
        assert len(events) == 1
        assert isinstance(events[0], TermDescriptionUpdated)
        assert events[0].term_id == term.id

    def test_update_term_description_too_long_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))
        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )

        with pytest.raises(TermDescriptionTooLongError):
            service.update_term_description(
                UpdateTermDescription(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_id=term.id,
                    description="x" * (MAX_TERM_DESCRIPTION_LENGTH + 1),
                )
            )

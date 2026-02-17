import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    AddTerm,
    CreateTaxonomy,
    MoveTerm,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.exceptions import (
    CannotBeOwnParentError,
    CircularReferenceError,
)
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


class TestMoveTerm:
    def test_move_to_new_parent_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        parent_a = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="A")
        )
        parent_b = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="B")
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent_a.id,
            )
        )
        uow.committed = False

        service.move_term(
            MoveTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=child.id,
                new_parent_id=parent_b.id,
            )
        )

        assert child.parent_term_id == parent_b.id
        assert uow.committed is True

    def test_move_to_root(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Parent")
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent.id,
            )
        )

        service.move_term(
            MoveTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=child.id,
                new_parent_id=None,
            )
        )

        assert child.parent_term_id is None

    def test_move_self_parent_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        term = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )

        with pytest.raises(CannotBeOwnParentError):
            service.move_term(
                MoveTerm(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_id=term.id,
                    new_parent_id=term.id,
                )
            )

    def test_move_cycle_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        grandparent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Grandparent")
        )
        parent = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Parent",
                parent_term_id=grandparent.id,
            )
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent.id,
            )
        )

        # Moving grandparent under child creates a cycle
        with pytest.raises(CircularReferenceError):
            service.move_term(
                MoveTerm(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_id=grandparent.id,
                    new_parent_id=child.id,
                )
            )

    def test_move_same_parent_is_noop(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = service.create_taxonomy(CreateTaxonomy(owner_id=owner_id, name="Categories"))

        parent = service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Parent")
        )
        child = service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent.id,
            )
        )

        service.move_term(
            MoveTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=child.id,
                new_parent_id=parent.id,
            )
        )

        assert child.parent_term_id == parent.id

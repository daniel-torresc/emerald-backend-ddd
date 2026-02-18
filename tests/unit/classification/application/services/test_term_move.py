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
    async def test_move_to_new_parent_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        parent_a = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="A")
        )
        parent_b = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="B")
        )
        child = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent_a.id,
            )
        )
        uow.committed = False

        await service.move_term(
            MoveTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=child.id,
                new_parent_id=parent_b.id,
            )
        )

        assert child.parent_term_id == parent_b.id
        assert uow.committed is True

    async def test_move_to_root(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        parent = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Parent")
        )
        child = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent.id,
            )
        )

        await service.move_term(
            MoveTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=child.id,
                new_parent_id=None,
            )
        )

        assert child.parent_term_id is None

    async def test_move_self_parent_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        term = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )

        with pytest.raises(CannotBeOwnParentError):
            await service.move_term(
                MoveTerm(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_id=term.id,
                    new_parent_id=term.id,
                )
            )

    async def test_move_cycle_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        grandparent = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Grandparent")
        )
        parent = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Parent",
                parent_term_id=grandparent.id,
            )
        )
        child = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent.id,
            )
        )

        # Moving grandparent under child creates a cycle
        with pytest.raises(CircularReferenceError):
            await service.move_term(
                MoveTerm(
                    taxonomy_id=taxonomy.id,
                    owner_id=owner_id,
                    term_id=grandparent.id,
                    new_parent_id=child.id,
                )
            )

    async def test_move_same_parent_is_noop(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        parent = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Parent")
        )
        child = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Child",
                parent_term_id=parent.id,
            )
        )

        await service.move_term(
            MoveTerm(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                term_id=child.id,
                new_parent_id=parent.id,
            )
        )

        assert child.parent_term_id == parent.id

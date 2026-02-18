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
    async def test_delete_term_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )
        term = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        uow.committed = False

        await service.delete_term(
            DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id)
        )

        assert term.is_deleted()
        assert uow.committed is True

    async def test_delete_term_cascade_descendants(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        parent = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        child = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )
        grandchild = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Apples",
                parent_term_id=child.id,
            )
        )

        await service.delete_term(
            DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=parent.id)
        )

        assert parent.is_deleted()
        assert child.is_deleted()
        assert grandchild.is_deleted()


class TestRecoverTerm:
    async def test_recover_term_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )
        term = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        await service.delete_term(
            DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id)
        )
        uow.committed = False

        await service.recover_term(
            RecoverTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=term.id)
        )

        assert term.is_active()
        assert uow.committed is True

    async def test_recover_term_parent_deleted_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            CreateTaxonomy(owner_id=owner_id, name="Categories")
        )

        parent = await service.add_term(
            _make_add_term_cmd(taxonomy_id=taxonomy.id, owner_id=owner_id, name="Food")
        )
        child = await service.add_term(
            _make_add_term_cmd(
                taxonomy_id=taxonomy.id,
                owner_id=owner_id,
                name="Fruits",
                parent_term_id=parent.id,
            )
        )

        # Delete parent (cascades to child)
        await service.delete_term(
            DeleteTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=parent.id)
        )

        # Try to recover child while parent is still deleted
        with pytest.raises(ParentTermDeletedError):
            await service.recover_term(
                RecoverTerm(taxonomy_id=taxonomy.id, owner_id=owner_id, term_id=child.id)
            )

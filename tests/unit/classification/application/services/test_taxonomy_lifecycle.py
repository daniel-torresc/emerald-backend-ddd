import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    CreateTaxonomy,
    RecoverTaxonomy,
    SoftDeleteTaxonomy,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.classification.fakes import FakeClassificationUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_service() -> tuple[TaxonomyManagementService, FakeClassificationUnitOfWork]:
    uow = FakeClassificationUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    service = TaxonomyManagementService(uow=uow, retention_policy_service=retention_service)
    return service, uow


def _make_create_cmd(**overrides: Any) -> CreateTaxonomy:
    defaults: dict[str, Any] = {
        "owner_id": uuid.uuid4(),
        "name": "My Taxonomy",
    }
    defaults.update(overrides)
    return CreateTaxonomy(**defaults)


class TestSoftDeleteTaxonomy:
    async def test_soft_delete_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))
        uow.committed = False

        await service.soft_delete_taxonomy(
            SoftDeleteTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
        )

        assert taxonomy.is_deleted()
        assert uow.committed is True

    async def test_soft_delete_commits(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))
        uow.committed = False

        await service.soft_delete_taxonomy(
            SoftDeleteTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
        )

        assert uow.committed is True

    async def test_soft_delete_uses_retention(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))

        await service.soft_delete_taxonomy(
            SoftDeleteTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
        )

        assert taxonomy.is_deleted()
        assert taxonomy.hard_delete_scheduled_at is not None

    async def test_soft_delete_already_deleted_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))

        await service.soft_delete_taxonomy(
            SoftDeleteTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
        )

        with pytest.raises(AlreadyDeletedError):
            await service.soft_delete_taxonomy(
                SoftDeleteTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
            )


class TestRecoverTaxonomy:
    async def test_recover_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))
        await service.soft_delete_taxonomy(
            SoftDeleteTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
        )
        uow.committed = False

        await service.recover_taxonomy(RecoverTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id))

        assert not taxonomy.is_deleted()
        assert uow.committed is True

    async def test_recover_not_deleted_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))

        with pytest.raises(NotDeletedError):
            await service.recover_taxonomy(
                RecoverTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id)
            )

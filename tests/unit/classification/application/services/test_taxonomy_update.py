import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import (
    CreateTaxonomy,
    RenameTaxonomy,
    UpdateTaxonomyDescription,
)
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.exceptions import (
    TaxonomyNameAlreadyExistsError,
    TaxonomyNotFoundError,
)
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
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


class TestRenameTaxonomy:
    async def test_rename_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            _make_create_cmd(owner_id=owner_id, name="Old Name")
        )
        uow.committed = False

        await service.rename_taxonomy(
            RenameTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id, new_name="New Name")
        )

        assert taxonomy.name == TaxonomyName("New Name")
        assert uow.committed is True

    async def test_rename_uniqueness_excludes_self(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            _make_create_cmd(owner_id=owner_id, name="Groceries")
        )

        # Renaming to same name (self-excluded) should succeed
        await service.rename_taxonomy(
            RenameTaxonomy(taxonomy_id=taxonomy.id, owner_id=owner_id, new_name="Groceries")
        )
        assert taxonomy.name == TaxonomyName("Groceries")

    async def test_rename_duplicate_name_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        await service.create_taxonomy(_make_create_cmd(owner_id=owner_id, name="Groceries"))
        taxonomy2 = await service.create_taxonomy(
            _make_create_cmd(owner_id=owner_id, name="Travel")
        )

        with pytest.raises(TaxonomyNameAlreadyExistsError):
            await service.rename_taxonomy(
                RenameTaxonomy(taxonomy_id=taxonomy2.id, owner_id=owner_id, new_name="Groceries")
            )

    async def test_rename_not_found_raises(self) -> None:
        service, uow = _make_service()
        with pytest.raises(TaxonomyNotFoundError):
            await service.rename_taxonomy(
                RenameTaxonomy(taxonomy_id=uuid.uuid4(), owner_id=uuid.uuid4(), new_name="Whatever")
            )

    async def test_rename_wrong_owner_raises_not_found(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id, name="Mine"))

        other_user = uuid.uuid4()
        with pytest.raises(TaxonomyNotFoundError):
            await service.rename_taxonomy(
                RenameTaxonomy(taxonomy_id=taxonomy.id, owner_id=other_user, new_name="Stolen")
            )


class TestUpdateTaxonomyDescription:
    async def test_update_description_success(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))
        uow.committed = False

        await service.update_taxonomy_description(
            UpdateTaxonomyDescription(
                taxonomy_id=taxonomy.id, owner_id=owner_id, description="New description"
            )
        )

        assert taxonomy.description == "New description"
        assert uow.committed is True

    async def test_update_description_to_none(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(
            _make_create_cmd(owner_id=owner_id, description="Initial desc")
        )

        await service.update_taxonomy_description(
            UpdateTaxonomyDescription(taxonomy_id=taxonomy.id, owner_id=owner_id, description=None)
        )

        assert taxonomy.description is None

    async def test_update_description_wrong_owner_raises_not_found(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        taxonomy = await service.create_taxonomy(_make_create_cmd(owner_id=owner_id))

        with pytest.raises(TaxonomyNotFoundError):
            await service.update_taxonomy_description(
                UpdateTaxonomyDescription(
                    taxonomy_id=taxonomy.id,
                    owner_id=uuid.uuid4(),
                    description="Hacked",
                )
            )

    async def test_update_description_not_found_raises(self) -> None:
        service, uow = _make_service()
        with pytest.raises(TaxonomyNotFoundError):
            await service.update_taxonomy_description(
                UpdateTaxonomyDescription(
                    taxonomy_id=uuid.uuid4(),
                    owner_id=uuid.uuid4(),
                    description="Something",
                )
            )

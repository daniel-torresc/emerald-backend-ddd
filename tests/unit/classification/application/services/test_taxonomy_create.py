import uuid
from typing import Any

import pytest

from emerald.classification.application.dtos.commands.taxonomy_commands import CreateTaxonomy
from emerald.classification.application.services.taxonomy_management import (
    TaxonomyManagementService,
)
from emerald.classification.domain.exceptions import TaxonomyNameAlreadyExistsError
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
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


def _make_cmd(**overrides: Any) -> CreateTaxonomy:
    defaults: dict[str, Any] = {
        "owner_id": uuid.uuid4(),
        "name": "My Taxonomy",
    }
    defaults.update(overrides)
    return CreateTaxonomy(**defaults)


class TestCreateTaxonomy:
    async def test_creates_taxonomy_and_returns_it(self) -> None:
        service, uow = _make_service()
        cmd = _make_cmd()
        taxonomy = await service.create_taxonomy(cmd)

        assert isinstance(taxonomy, Taxonomy)
        assert taxonomy.name == TaxonomyName("My Taxonomy")
        assert taxonomy.owner_id == cmd.owner_id
        assert taxonomy.description is None

    async def test_saves_to_repository(self) -> None:
        service, uow = _make_service()
        cmd = _make_cmd()
        taxonomy = await service.create_taxonomy(cmd)

        found = uow.taxonomies.find_by_id(taxonomy.id)
        assert found is not None
        assert found.id == taxonomy.id

    async def test_commits_unit_of_work(self) -> None:
        service, uow = _make_service()
        cmd = _make_cmd()
        await service.create_taxonomy(cmd)

        assert uow.committed is True

    async def test_with_description(self) -> None:
        service, uow = _make_service()
        cmd = _make_cmd(description="A custom taxonomy for groceries")
        taxonomy = await service.create_taxonomy(cmd)

        assert taxonomy.description == "A custom taxonomy for groceries"


class TestCreateTaxonomyUniqueness:
    async def test_duplicate_name_for_same_owner_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        cmd1 = _make_cmd(owner_id=owner_id, name="Groceries")
        await service.create_taxonomy(cmd1)

        cmd2 = _make_cmd(owner_id=owner_id, name="Groceries")
        with pytest.raises(TaxonomyNameAlreadyExistsError):
            await service.create_taxonomy(cmd2)

    async def test_duplicate_name_case_insensitive_raises(self) -> None:
        service, uow = _make_service()
        owner_id = uuid.uuid4()
        cmd1 = _make_cmd(owner_id=owner_id, name="Groceries")
        await service.create_taxonomy(cmd1)

        cmd2 = _make_cmd(owner_id=owner_id, name="GROCERIES")
        with pytest.raises(TaxonomyNameAlreadyExistsError):
            await service.create_taxonomy(cmd2)

    async def test_same_name_different_owners_allowed(self) -> None:
        service, uow = _make_service()
        cmd1 = _make_cmd(owner_id=uuid.uuid4(), name="Groceries")
        await service.create_taxonomy(cmd1)

        cmd2 = _make_cmd(owner_id=uuid.uuid4(), name="Groceries")
        taxonomy = await service.create_taxonomy(cmd2)
        assert taxonomy is not None

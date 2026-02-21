"""Integration tests for SqlAlchemyRetentionPolicyRepository."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)
from emerald.shared_kernel.adapters.outbound.persistence.retention_policy_repository import (
    SqlAlchemyRetentionPolicyRepository,
)
from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)

# Reuse user factory from IAM tests
from tests.integration.iam.conftest import make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    user = make_user()
    repo = SqlAlchemyUserRepository(session)
    await repo.add(user)
    await session.flush()
    return user.id


class TestRetentionPolicyRepository:
    async def test_save_and_find(
        self,
        retention_repo: SqlAlchemyRetentionPolicyRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        pref = UserRetentionPreference(
            user_id=user_id,
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(duration=60, unit=RetentionUnit.DAYS),
        )
        await retention_repo.save_user_preference(pref)
        await session.flush()

        found = await retention_repo.find_user_preference(DeletableEntityType.USER, user_id)
        assert found is not None
        assert found.user_id == user_id
        assert found.entity_type == DeletableEntityType.USER
        assert found.retention_period.duration == 60
        assert found.retention_period.unit == RetentionUnit.DAYS

    async def test_find_returns_none(
        self,
        retention_repo: SqlAlchemyRetentionPolicyRepository,
        session: AsyncSession,
    ) -> None:
        found = await retention_repo.find_user_preference(DeletableEntityType.USER, uuid.uuid4())
        assert found is None

    async def test_upsert_existing(
        self,
        retention_repo: SqlAlchemyRetentionPolicyRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        pref = UserRetentionPreference(
            user_id=user_id,
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            retention_period=RetentionPeriod(duration=8, unit=RetentionUnit.YEARS),
        )
        await retention_repo.save_user_preference(pref)
        await session.flush()

        # Update with higher retention
        pref2 = UserRetentionPreference(
            id=pref.id,
            user_id=user_id,
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            retention_period=RetentionPeriod(duration=10, unit=RetentionUnit.YEARS),
        )
        await retention_repo.save_user_preference(pref2)
        await session.flush()

        found = await retention_repo.find_user_preference(
            DeletableEntityType.FINANCIAL_ACCOUNT, user_id
        )
        assert found is not None
        assert found.retention_period.duration == 10

    async def test_delete_preference(
        self,
        retention_repo: SqlAlchemyRetentionPolicyRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        pref = UserRetentionPreference(
            user_id=user_id,
            entity_type=DeletableEntityType.CARD,
            retention_period=RetentionPeriod(duration=180, unit=RetentionUnit.DAYS),
        )
        await retention_repo.save_user_preference(pref)
        await session.flush()

        await retention_repo.delete_user_preference(DeletableEntityType.CARD, user_id)
        await session.flush()

        found = await retention_repo.find_user_preference(DeletableEntityType.CARD, user_id)
        assert found is None

    async def test_delete_nonexistent_no_error(
        self,
        retention_repo: SqlAlchemyRetentionPolicyRepository,
        session: AsyncSession,
    ) -> None:
        await retention_repo.delete_user_preference(DeletableEntityType.USER, uuid.uuid4())

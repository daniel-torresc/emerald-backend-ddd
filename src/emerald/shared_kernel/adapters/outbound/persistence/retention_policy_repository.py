"""SQLAlchemy implementation of the RetentionPolicyRepository protocol."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.shared_kernel.adapters.outbound.persistence.orm_models import (
    UserRetentionPreferenceModel,
)
from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class SqlAlchemyRetentionPolicyRepository:
    """RetentionPolicyRepository backed by SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> UserRetentionPreference | None:
        stmt = sa.select(UserRetentionPreferenceModel).where(
            UserRetentionPreferenceModel.user_id == user_id,
            UserRetentionPreferenceModel.entity_type == entity_type.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def save_user_preference(self, preference: UserRetentionPreference) -> None:
        model = UserRetentionPreferenceModel.from_domain(preference)
        await self._session.merge(model)

    async def delete_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> None:
        stmt = sa.delete(UserRetentionPreferenceModel).where(
            UserRetentionPreferenceModel.user_id == user_id,
            UserRetentionPreferenceModel.entity_type == entity_type.value,
        )
        await self._session.execute(stmt)

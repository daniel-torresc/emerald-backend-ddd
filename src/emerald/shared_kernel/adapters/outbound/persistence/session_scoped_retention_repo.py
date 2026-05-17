"""Retention policy repository that opens its own session per method call.

Used by the DI container to provide a standalone RetentionPolicyService
that works outside of a Unit of Work context.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)

from .retention_policy_repository import SqlAlchemyRetentionPolicyRepository


class SessionPerCallRetentionPolicyRepository:
    """Wraps SqlAlchemyRetentionPolicyRepository with a fresh session per call.

    Satisfies the RetentionPolicyRepository protocol via structural subtyping.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> UserRetentionPreference | None:
        async with self._session_factory() as session:
            repo = SqlAlchemyRetentionPolicyRepository(session)
            return await repo.find_user_preference(entity_type, user_id)

    async def save_user_preference(self, preference: UserRetentionPreference) -> None:
        async with self._session_factory() as session:
            repo = SqlAlchemyRetentionPolicyRepository(session)
            await repo.save_user_preference(preference)
            await session.commit()

    async def delete_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> None:
        async with self._session_factory() as session:
            repo = SqlAlchemyRetentionPolicyRepository(session)
            await repo.delete_user_preference(entity_type, user_id)
            await session.commit()

"""SQLAlchemy implementation of the RefreshTokenRepository protocol."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.iam.adapters.outbound.persistence.orm_models import RefreshTokenModel
from emerald.iam.domain.models.entities.refresh_token import RefreshToken


class SqlAlchemyRefreshTokenRepository:
    """RefreshTokenRepository backed by SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> None:
        model = RefreshTokenModel.from_domain(token)
        self._session.add(model)

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = sa.select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def find_active_families_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = sa.select(sa.distinct(RefreshTokenModel.family_id)).where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
            RefreshTokenModel.expires_at > sa.func.now(),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        stmt = (
            sa.update(RefreshTokenModel)
            .where(
                RefreshTokenModel.family_id == family_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=sa.func.now())
        )
        await self._session.execute(stmt)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = (
            sa.update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=sa.func.now())
        )
        await self._session.execute(stmt)

    async def count_active_families(self, user_id: uuid.UUID) -> int:
        stmt = sa.select(sa.func.count(sa.distinct(RefreshTokenModel.family_id))).where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
            RefreshTokenModel.expires_at > sa.func.now(),
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

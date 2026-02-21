"""SQLAlchemy implementation of the PasswordResetTokenRepository protocol."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.iam.adapters.outbound.persistence.orm_models import PasswordResetTokenModel
from emerald.iam.domain.models.entities.password_reset_token import PasswordResetToken


class SqlAlchemyPasswordResetTokenRepository:
    """PasswordResetTokenRepository backed by SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: PasswordResetToken) -> None:
        model = PasswordResetTokenModel.from_domain(token)
        self._session.add(model)

    async def find_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        stmt = sa.select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.token_hash == token_hash
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def invalidate_existing_for_user(self, user_id: uuid.UUID) -> None:
        stmt = (
            sa.update(PasswordResetTokenModel)
            .where(
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.used_at.is_(None),
            )
            .values(used_at=sa.func.now())
        )
        await self._session.execute(stmt)

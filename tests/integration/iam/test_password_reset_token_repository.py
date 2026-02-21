"""Integration tests for SqlAlchemyPasswordResetTokenRepository."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.iam.adapters.outbound.persistence.password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)
from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)

from .conftest import make_password_reset_token, make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    user = make_user()
    repo = SqlAlchemyUserRepository(session)
    await repo.add(user)
    await session.flush()
    return user.id


class TestPasswordResetTokenAdd:
    async def test_add_and_find_by_hash(
        self,
        password_reset_token_repo: SqlAlchemyPasswordResetTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        token = make_password_reset_token(user_id)
        await password_reset_token_repo.add(token)
        await session.flush()

        found = await password_reset_token_repo.find_by_hash(token.token_hash)
        assert found is not None
        assert found.id == token.id
        assert found.user_id == user_id
        assert found.used_at is None

    async def test_find_by_hash_not_found(
        self,
        password_reset_token_repo: SqlAlchemyPasswordResetTokenRepository,
        session: AsyncSession,
    ) -> None:
        found = await password_reset_token_repo.find_by_hash("no-such-hash")
        assert found is None


class TestPasswordResetTokenInvalidate:
    async def test_invalidate_existing_for_user(
        self,
        password_reset_token_repo: SqlAlchemyPasswordResetTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        t1 = make_password_reset_token(user_id)
        t2 = make_password_reset_token(user_id)
        await password_reset_token_repo.add(t1)
        await password_reset_token_repo.add(t2)
        await session.flush()

        await password_reset_token_repo.invalidate_existing_for_user(user_id)
        await session.flush()

        found1 = await password_reset_token_repo.find_by_hash(t1.token_hash)
        found2 = await password_reset_token_repo.find_by_hash(t2.token_hash)
        assert found1 is not None and found1.used_at is not None
        assert found2 is not None and found2.used_at is not None

    async def test_invalidate_no_op_when_none_active(
        self,
        password_reset_token_repo: SqlAlchemyPasswordResetTokenRepository,
        session: AsyncSession,
    ) -> None:
        await password_reset_token_repo.invalidate_existing_for_user(uuid.uuid4())

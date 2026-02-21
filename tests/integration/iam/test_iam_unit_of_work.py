"""Integration tests for SqlAlchemyIamUnitOfWork."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from emerald.iam.adapters.outbound.persistence.unit_of_work import (
    SqlAlchemyIamUnitOfWork,
)
from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)

from .conftest import make_refresh_token, make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestIamUnitOfWork:
    async def test_repos_share_same_session(self, iam_uow: SqlAlchemyIamUnitOfWork) -> None:
        async with iam_uow:
            # All repos should use the same underlying session
            assert iam_uow.users._session is iam_uow.refresh_tokens._session
            assert iam_uow.users._session is iam_uow.password_reset_tokens._session

    async def test_commit_persists_across_repos(
        self,
        iam_uow: SqlAlchemyIamUnitOfWork,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        user = make_user()

        async with iam_uow:
            await iam_uow.users.add(user)
            await iam_uow.session.flush()  # FK: token references user
            token = make_refresh_token(user.id)
            await iam_uow.refresh_tokens.add(token)
            await iam_uow.commit()

        # Verify with a fresh session
        async with session_factory() as sess:
            repo = SqlAlchemyUserRepository(sess)
            found = await repo.find_by_id(user.id)
            assert found is not None

    async def test_rollback_discards_all_changes(
        self,
        iam_uow: SqlAlchemyIamUnitOfWork,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        user = make_user()

        async with iam_uow:
            await iam_uow.users.add(user)
            await iam_uow.rollback()

        # User should not exist
        async with session_factory() as sess:
            repo = SqlAlchemyUserRepository(sess)
            found = await repo.find_by_id(user.id)
            assert found is None

    async def test_repos_reset_on_reentry(self, iam_uow: SqlAlchemyIamUnitOfWork) -> None:
        async with iam_uow:
            users1 = iam_uow.users

        async with iam_uow:
            users2 = iam_uow.users

        # Different repo instances because new session each time
        assert users1 is not users2

    async def test_repos_cached_within_context(self, iam_uow: SqlAlchemyIamUnitOfWork) -> None:
        async with iam_uow:
            users1 = iam_uow.users
            users2 = iam_uow.users
            assert users1 is users2

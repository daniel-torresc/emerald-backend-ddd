"""Integration tests for SqlAlchemyRefreshTokenRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.iam.adapters.outbound.persistence.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)
from emerald.iam.domain.models.value_objects.portal_context import PortalContext

from .conftest import make_refresh_token, make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _insert_user(session: AsyncSession) -> uuid.UUID:
    """Helper: insert a user and return their ID."""
    user = make_user()
    repo = SqlAlchemyUserRepository(session)
    await repo.add(user)
    await session.flush()
    return user.id


class TestRefreshTokenAdd:
    async def test_add_and_find_by_hash(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        token = make_refresh_token(user_id)
        await refresh_token_repo.add(token)
        await session.flush()

        found = await refresh_token_repo.find_by_hash(token.token_hash)
        assert found is not None
        assert found.id == token.id
        assert found.user_id == user_id
        assert found.family_id == token.family_id
        assert found.portal_context == PortalContext.REGULAR
        assert found.revoked_at is None

    async def test_find_by_hash_not_found(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        found = await refresh_token_repo.find_by_hash("nonexistent-hash")
        assert found is None


class TestRefreshTokenFamilies:
    async def test_find_active_families(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        family1 = uuid.uuid4()
        family2 = uuid.uuid4()

        # Active tokens in two families
        await refresh_token_repo.add(make_refresh_token(user_id, family_id=family1))
        await refresh_token_repo.add(make_refresh_token(user_id, family_id=family2))
        # Expired token in a third family
        await refresh_token_repo.add(
            make_refresh_token(
                user_id,
                family_id=uuid.uuid4(),
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        # Revoked token in a fourth family
        await refresh_token_repo.add(
            make_refresh_token(
                user_id,
                family_id=uuid.uuid4(),
                revoked_at=datetime.now(UTC),
            )
        )
        await session.flush()

        active = await refresh_token_repo.find_active_families_by_user(user_id)
        assert len(active) == 2
        assert set(active) == {family1, family2}

    async def test_count_active_families(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        family1 = uuid.uuid4()
        family2 = uuid.uuid4()

        await refresh_token_repo.add(make_refresh_token(user_id, family_id=family1))
        await refresh_token_repo.add(make_refresh_token(user_id, family_id=family2))
        await session.flush()

        count = await refresh_token_repo.count_active_families(user_id)
        assert count == 2


class TestRefreshTokenRevoke:
    async def test_revoke_family(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        family_id = uuid.uuid4()

        t1 = make_refresh_token(user_id, family_id=family_id)
        t2 = make_refresh_token(user_id, family_id=family_id)
        await refresh_token_repo.add(t1)
        await refresh_token_repo.add(t2)
        await session.flush()

        await refresh_token_repo.revoke_family(family_id)
        await session.flush()

        found1 = await refresh_token_repo.find_by_hash(t1.token_hash)
        found2 = await refresh_token_repo.find_by_hash(t2.token_hash)
        assert found1 is not None and found1.revoked_at is not None
        assert found2 is not None and found2.revoked_at is not None

    async def test_revoke_all_for_user(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        user_id = await _insert_user(session)
        t1 = make_refresh_token(user_id, family_id=uuid.uuid4())
        t2 = make_refresh_token(user_id, family_id=uuid.uuid4())
        await refresh_token_repo.add(t1)
        await refresh_token_repo.add(t2)
        await session.flush()

        await refresh_token_repo.revoke_all_for_user(user_id)
        await session.flush()

        found1 = await refresh_token_repo.find_by_hash(t1.token_hash)
        found2 = await refresh_token_repo.find_by_hash(t2.token_hash)
        assert found1 is not None and found1.revoked_at is not None
        assert found2 is not None and found2.revoked_at is not None

    async def test_revoke_no_op_when_none_active(
        self,
        refresh_token_repo: SqlAlchemyRefreshTokenRepository,
        session: AsyncSession,
    ) -> None:
        """Revoking with no matching rows should not error."""
        await refresh_token_repo.revoke_family(uuid.uuid4())
        await refresh_token_repo.revoke_all_for_user(uuid.uuid4())

"""SQLAlchemy implementation of the IAM Unit of Work."""

from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from emerald.iam.adapters.outbound.persistence.password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)
from emerald.iam.adapters.outbound.persistence.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)
from emerald.shared_kernel.adapters.outbound.persistence.base_unit_of_work import (
    SqlAlchemyUnitOfWork,
)


class SqlAlchemyIamUnitOfWork(SqlAlchemyUnitOfWork):
    """IAM Unit of Work — exposes users, refresh_tokens, password_reset_tokens repos.

    All repositories share the same AsyncSession for transactional atomicity.
    Repository instances are lazily created and cached per ``async with`` block.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)
        self._users: SqlAlchemyUserRepository | None = None
        self._refresh_tokens: SqlAlchemyRefreshTokenRepository | None = None
        self._password_reset_tokens: SqlAlchemyPasswordResetTokenRepository | None = None

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        # Reset cached repos — new session means new repos
        self._users = None
        self._refresh_tokens = None
        self._password_reset_tokens = None
        return self

    @property
    def users(self) -> SqlAlchemyUserRepository:
        if self._users is None:
            self._users = SqlAlchemyUserRepository(self.session)
        return self._users

    @property
    def refresh_tokens(self) -> SqlAlchemyRefreshTokenRepository:
        if self._refresh_tokens is None:
            self._refresh_tokens = SqlAlchemyRefreshTokenRepository(self.session)
        return self._refresh_tokens

    @property
    def password_reset_tokens(self) -> SqlAlchemyPasswordResetTokenRepository:
        if self._password_reset_tokens is None:
            self._password_reset_tokens = SqlAlchemyPasswordResetTokenRepository(self.session)
        return self._password_reset_tokens

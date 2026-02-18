"""Base SQLAlchemy async Unit of Work."""

from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlAlchemyUnitOfWork:
    """Async Unit of Work backed by a SQLAlchemy session.

    Usage::

        async with uow:
            entity = await uow.some_repo.find_by_id(...)
            entity.do_something()
            await uow.commit()
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.rollback()
        assert self._session is not None
        await self._session.close()

    async def commit(self) -> None:
        """Persist changes."""
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        """Discard uncommitted changes."""
        assert self._session is not None
        await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        """The current session — available after __aenter__."""
        assert self._session is not None
        return self._session

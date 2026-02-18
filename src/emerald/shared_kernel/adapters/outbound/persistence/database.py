"""Async database engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from emerald.shared_kernel.infrastructure.config.settings import DatabaseSettings


def create_async_engine_from_settings(settings: DatabaseSettings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from database settings."""
    return create_async_engine(
        settings.url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        echo=settings.echo,
        echo_pool=settings.echo_pool,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_engine(engine: AsyncEngine) -> None:
    """Dispose the engine and its connection pool."""
    await engine.dispose()

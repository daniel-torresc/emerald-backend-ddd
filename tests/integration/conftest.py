"""Shared integration test fixtures: PostgreSQL container, engine, session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

# Import ORM models so their tables are registered on Base.metadata
import emerald.iam.adapters.outbound.persistence.orm_models  # noqa: F401
import emerald.shared_kernel.adapters.outbound.persistence.orm_models  # noqa: F401
from emerald.shared_kernel.adapters.outbound.persistence.orm_base import Base


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer]:
    """Start a PostgreSQL container for the test session."""
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def async_engine(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncEngine]:
    """Create an async engine connected to the test container."""
    url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _create_tables(async_engine: AsyncEngine) -> AsyncGenerator[None]:
    """Create all tables before tests run, drop after."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def session_factory(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory for tests."""
    return async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture(loop_scope="session")
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    """Per-test session with rollback isolation."""
    async with session_factory() as sess:
        async with sess.begin():
            yield sess
            await sess.rollback()

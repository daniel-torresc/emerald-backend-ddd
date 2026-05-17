"""Core container — settings, database engine, session factory, retention service."""

from __future__ import annotations

from collections.abc import AsyncIterator

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from emerald.shared_kernel.adapters.outbound.persistence.database import (
    create_async_engine_from_settings,
    create_session_factory,
)
from emerald.shared_kernel.adapters.outbound.persistence.session_scoped_retention_repo import (
    SessionPerCallRetentionPolicyRepository,
)
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from emerald.shared_kernel.infrastructure.config.settings import AppSettings


async def init_engine(settings: AppSettings) -> AsyncIterator[AsyncEngine]:
    """Async resource: create engine on startup, dispose on shutdown."""
    engine = create_async_engine_from_settings(settings.database)
    yield engine
    await engine.dispose()


class CoreContainer(containers.DeclarativeContainer):
    """Shared kernel providers: settings, DB, retention."""

    settings = providers.Singleton(AppSettings)

    engine: providers.Resource[AsyncEngine] = providers.Resource(
        init_engine,
        settings=settings,
    )

    session_factory: providers.Singleton[async_sessionmaker[AsyncSession]] = providers.Singleton(
        create_session_factory,
        engine=engine,
    )

    _retention_repo = providers.Singleton(
        SessionPerCallRetentionPolicyRepository,
        session_factory=session_factory,
    )

    retention_policy_service = providers.Singleton(
        RetentionPolicyService,
        preference_repository=_retention_repo,
    )

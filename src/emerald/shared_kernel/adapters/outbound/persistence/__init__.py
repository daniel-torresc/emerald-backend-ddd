"""Persistence adapters — ORM registry, engine, session, base UoW.

Import directly from specific modules:
    from emerald.shared_kernel.adapters.outbound.persistence.orm_registry import metadata
    from emerald.shared_kernel.adapters.outbound.persistence.database import (
        create_async_engine_from_settings,
    )
    from emerald.shared_kernel.adapters.outbound.persistence.base_unit_of_work import (
        SqlAlchemyUnitOfWork,
    )
    from emerald.shared_kernel.adapters.outbound.persistence.mapper_setup import (
        configure_all_mappers,
    )
"""

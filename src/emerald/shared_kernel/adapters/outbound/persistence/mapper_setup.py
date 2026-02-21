"""Composition root mapper configuration.

Calls each context's configure_*_mappers() function once during app bootstrap.
Also called by Alembic env.py before autogenerate so it can see all mapped tables.

Context-specific mapper registrations will be added by specs 022-025.
"""

from __future__ import annotations


def configure_all_mappers() -> None:
    """Register all domain class -> table mappings.

    Called once during app startup and by Alembic env.py.
    Importing ORM model modules is sufficient to register their tables with
    the shared MetaData.
    """
    import emerald.iam.adapters.outbound.persistence.orm_models  # noqa: F401
    import emerald.shared_kernel.adapters.outbound.persistence.orm_models  # noqa: F401

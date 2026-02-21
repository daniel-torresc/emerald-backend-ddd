"""Shared declarative base for all ORM models across bounded contexts."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

from emerald.shared_kernel.adapters.outbound.persistence.orm_registry import metadata as _metadata


class Base(DeclarativeBase):
    """ORM base class tied to the shared MetaData instance.

    All context-specific ORM models inherit from this base, ensuring they share
    the same MetaData (and thus naming conventions, table registry, etc.).
    """

    metadata = _metadata

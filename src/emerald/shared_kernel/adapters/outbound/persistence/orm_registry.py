"""Shared ORM registry and column helpers for classical/imperative mapping.

All context-specific table definitions and mappers import from here.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import registry

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = sa.MetaData(naming_convention=convention)
mapper_registry = registry(metadata=metadata)


def uuid_pk() -> list[sa.Column[Any]]:
    """UUID primary key column."""
    return [sa.Column("id", sa.Uuid, primary_key=True, nullable=False)]


def timestamp_columns() -> list[sa.Column[Any]]:
    """Created/updated timestamp columns (timezone-aware)."""
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    ]


def audit_columns() -> list[sa.Column[Any]]:
    """Timestamp + actor tracking columns for auditable entities."""
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("created_by", sa.Uuid, nullable=False),
        sa.Column("updated_by", sa.Uuid, nullable=True),
    ]


def soft_delete_columns() -> list[sa.Column[Any]]:
    """Soft-delete columns matching SoftDeletableMixin fields."""
    return [
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid, nullable=True),
        sa.Column("deletion_reason", sa.String, nullable=True),
        sa.Column("hard_delete_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    ]


def version_column() -> list[sa.Column[Any]]:
    """Optimistic concurrency version column."""
    return [sa.Column("version", sa.Integer, nullable=False, default=0, server_default="0")]

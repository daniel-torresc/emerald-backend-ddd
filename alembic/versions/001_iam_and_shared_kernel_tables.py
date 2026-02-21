"""IAM and shared kernel tables.

Revision ID: 001
Revises:
Create Date: 2026-02-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. iam_users — root table, no FKs
    op.create_table(
        "iam_users",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("password_history", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("system_role", sa.String(20), nullable=False, server_default="USER"),
        sa.Column("admin_permissions", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "email_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("preferences_timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("preferences_locale", sa.String(20), nullable=False, server_default="en-US"),
        sa.Column(
            "preferences_display_currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspension_reason", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
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
        ),
        sa.Column("created_by", sa.Uuid, nullable=False),
        sa.Column("updated_by", sa.Uuid, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid, nullable=True),
        sa.Column("deletion_reason", sa.Text, nullable=True),
        sa.Column("hard_delete_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_iam_users_email", "iam_users", ["email"], unique=True)
    op.create_index(
        "ix_iam_users_username",
        "iam_users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("username IS NOT NULL"),
    )
    op.create_index("ix_iam_users_status", "iam_users", ["status"])
    op.create_index("ix_iam_users_system_role", "iam_users", ["system_role"])

    # 2. iam_user_auth_providers — FK → iam_users
    op.create_table(
        "iam_user_auth_providers",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid,
            sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_type", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "provider_type", name="uq_iam_user_auth_providers_user_provider"
        ),
    )
    op.create_index(
        "ix_iam_user_auth_providers_provider_external",
        "iam_user_auth_providers",
        ["provider_type", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    # 3. iam_refresh_tokens — FK → iam_users
    op.create_table(
        "iam_refresh_tokens",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid,
            sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("family_id", sa.Uuid, nullable=False),
        sa.Column("portal_context", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_iam_refresh_tokens_user_id", "iam_refresh_tokens", ["user_id"])
    op.create_index(
        "ix_iam_refresh_tokens_token_hash",
        "iam_refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_iam_refresh_tokens_family_id", "iam_refresh_tokens", ["family_id"])

    # 4. iam_password_reset_tokens — FK → iam_users
    op.create_table(
        "iam_password_reset_tokens",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid,
            sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_iam_password_reset_tokens_user_id",
        "iam_password_reset_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_iam_password_reset_tokens_token_hash",
        "iam_password_reset_tokens",
        ["token_hash"],
        unique=True,
    )

    # 5. sk_user_retention_preferences — FK → iam_users
    op.create_table(
        "sk_user_retention_preferences",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid,
            sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("retention_duration", sa.Integer, nullable=False),
        sa.Column("retention_unit", sa.String(10), nullable=False),
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
        ),
        sa.UniqueConstraint(
            "user_id", "entity_type", name="uq_sk_user_retention_preferences_user_entity"
        ),
    )


def downgrade() -> None:
    op.drop_table("sk_user_retention_preferences")
    op.drop_table("iam_password_reset_tokens")
    op.drop_table("iam_refresh_tokens")
    op.drop_table("iam_user_auth_providers")
    op.drop_table("iam_users")

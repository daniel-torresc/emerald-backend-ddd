"""IAM ORM models — separate from domain entities, with to_domain/from_domain converters."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.admin_permission import (
    AdminPermission,
    AdminPermissionType,
)
from emerald.iam.domain.models.value_objects.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.portal_context import PortalContext
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_preferences import UserPreferences
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from emerald.shared_kernel.adapters.outbound.persistence.orm_base import Base
from emerald.shared_kernel.domain.models import Currency


class UserAuthProviderModel(Base):
    """ORM model for iam_user_auth_providers table."""

    __tablename__ = "iam_user_auth_providers"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    external_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "user_id",
            "provider_type",
            name="uq_iam_user_auth_providers_user_provider",
        ),
        sa.Index(
            "ix_iam_user_auth_providers_provider_external",
            "provider_type",
            "external_id",
            unique=True,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        ),
    )

    @staticmethod
    def from_domain(user_id: uuid.UUID, provider: AuthProvider) -> UserAuthProviderModel:
        model = UserAuthProviderModel()
        model.id = uuid.uuid4()
        model.user_id = user_id
        model.provider_type = provider.provider_type.value
        model.external_id = provider.external_id
        model.linked_at = provider.linked_at
        return model

    def to_domain(self) -> AuthProvider:
        return AuthProvider(
            provider_type=ProviderType(self.provider_type),
            external_id=self.external_id,
            linked_at=self.linked_at,
        )


class UserModel(Base):
    """ORM model for iam_users table."""

    __tablename__ = "iam_users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    password_history: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    full_name: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    system_role: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="USER")
    admin_permissions: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    email_verified: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    preferences_timezone: Mapped[str] = mapped_column(
        sa.String(50), nullable=False, server_default="UTC"
    )
    preferences_locale: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="en-US"
    )
    preferences_display_currency: Mapped[str] = mapped_column(
        sa.String(3), nullable=False, server_default="USD"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    suspension_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    created_by: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    deletion_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    hard_delete_scheduled_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    auth_providers: Mapped[list[UserAuthProviderModel]] = relationship(
        UserAuthProviderModel,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_iam_users_email", "email", unique=True),
        sa.Index(
            "ix_iam_users_username",
            "username",
            unique=True,
            postgresql_where=sa.text("username IS NOT NULL"),
        ),
        sa.Index("ix_iam_users_status", "status"),
        sa.Index("ix_iam_users_system_role", "system_role"),
    )

    @staticmethod
    def from_domain(user: User) -> UserModel:
        model = UserModel()
        model.id = user.id
        model.email = user.email.value
        model.username = user.username.value if user.username is not None else None
        model.hashed_password = user.password.hashed_value if user.password is not None else None
        model.password_history = list(user.password_history)
        model.full_name = user.full_name
        model.status = user.status.value
        model.system_role = user.system_role.value
        model.admin_permissions = (
            [p.value.value for p in user.admin_permissions] if user.admin_permissions else []
        )
        model.email_verified = user.email_verified
        model.preferences_timezone = user.preferences.timezone
        model.preferences_locale = user.preferences.locale
        model.preferences_display_currency = user.preferences.display_currency.code
        model.last_login_at = user.last_login_at
        model.suspension_reason = user.suspension_reason
        model.version = user.version
        model.created_at = user.created_at
        model.updated_at = user.updated_at
        model.created_by = user.created_by
        model.updated_by = user.updated_by
        model.deleted_at = user.deleted_at
        model.deleted_by = user.deleted_by
        model.deletion_reason = user.deletion_reason
        model.hard_delete_scheduled_at = user.hard_delete_scheduled_at
        return model

    def to_domain(self) -> User:
        password = (
            HashedPassword(hashed_value=self.hashed_password)
            if self.hashed_password is not None
            else None
        )
        username = Username(value=self.username) if self.username is not None else None
        auth_providers = {p.to_domain() for p in self.auth_providers}
        admin_perms = frozenset(
            AdminPermission(AdminPermissionType(p)) for p in (self.admin_permissions or [])
        )

        user = User(
            email=EmailAddress(value=self.email),
            username=username,
            password=password,
            password_history=list(self.password_history or []),
            auth_providers=auth_providers,
            status=UserStatus(self.status),
            email_verified=self.email_verified,
            preferences=UserPreferences(
                timezone=self.preferences_timezone,
                locale=self.preferences_locale,
                display_currency=Currency[self.preferences_display_currency],
            ),
            full_name=self.full_name,
            last_login_at=self.last_login_at,
            suspension_reason=self.suspension_reason,
            system_role=SystemRole(self.system_role),
            admin_permissions=admin_perms if admin_perms else None,
            id=self.id,
            created_by=self.created_by,
            version=self.version,
            created_at=self.created_at,
        )
        # Hydrate mixin fields not in __init__
        user.updated_at = self.updated_at
        user.updated_by = self.updated_by
        user.deleted_at = self.deleted_at
        user.deleted_by = self.deleted_by
        user.deletion_reason = self.deletion_reason
        user.hard_delete_scheduled_at = self.hard_delete_scheduled_at
        # Clear any events registered during construction
        user.collect_events()
        return user


class RefreshTokenModel(Base):
    """ORM model for iam_refresh_tokens table."""

    __tablename__ = "iam_refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    portal_context: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_iam_refresh_tokens_user_id", "user_id"),
        sa.Index("ix_iam_refresh_tokens_token_hash", "token_hash", unique=True),
        sa.Index("ix_iam_refresh_tokens_family_id", "family_id"),
    )

    @staticmethod
    def from_domain(token: RefreshToken) -> RefreshTokenModel:
        model = RefreshTokenModel()
        model.id = token.id
        model.user_id = token.user_id
        model.token_hash = token.token_hash
        model.family_id = token.family_id
        model.portal_context = token.portal_context.value
        model.expires_at = token.expires_at
        model.created_at = token.created_at
        model.revoked_at = token.revoked_at
        return model

    def to_domain(self) -> RefreshToken:
        return RefreshToken(
            id=self.id,
            user_id=self.user_id,
            token_hash=self.token_hash,
            family_id=self.family_id,
            portal_context=PortalContext(self.portal_context),
            expires_at=self.expires_at,
            created_at=self.created_at,
            revoked_at=self.revoked_at,
        )


class PasswordResetTokenModel(Base):
    """ORM model for iam_password_reset_tokens table."""

    __tablename__ = "iam_password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_iam_password_reset_tokens_user_id", "user_id"),
        sa.Index("ix_iam_password_reset_tokens_token_hash", "token_hash", unique=True),
    )

    @staticmethod
    def from_domain(token: PasswordResetToken) -> PasswordResetTokenModel:
        model = PasswordResetTokenModel()
        model.id = token.id
        model.user_id = token.user_id
        model.token_hash = token.token_hash
        model.expires_at = token.expires_at
        model.created_at = token.created_at
        model.used_at = token.used_at
        return model

    def to_domain(self) -> PasswordResetToken:
        return PasswordResetToken(
            id=self.id,
            user_id=self.user_id,
            token_hash=self.token_hash,
            expires_at=self.expires_at,
            created_at=self.created_at,
            used_at=self.used_at,
        )

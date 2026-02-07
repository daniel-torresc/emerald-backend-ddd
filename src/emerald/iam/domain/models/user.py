from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from emerald.iam.domain.events.user_events import (
    AuthProviderLinked,
    AuthProviderUnlinked,
    EmailVerified,
    PasswordChanged,
    UserEmailChanged,
    UserLoggedIn,
    UserRecovered,
    UserRegistered,
    UserSoftDeleted,
    UserSuspended,
    UserUnsuspended,
    UserUsernameChanged,
)
from emerald.iam.domain.exceptions import (
    CannotUnlinkLastProviderError,
    InvalidStateTransitionError,
    PasswordAlreadySetError,
    ProviderAlreadyLinkedError,
    ProviderNotLinkedError,
)
from emerald.iam.domain.models.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.hashed_password import HashedPassword
from emerald.iam.domain.models.user_preferences import UserPreferences
from emerald.iam.domain.models.user_status import UserStatus
from emerald.iam.domain.models.username import Username
from emerald.shared_kernel.domain.models.aggregate_root import AggregateRoot
from emerald.shared_kernel.domain.models.auditable import AuditableMixin
from emerald.shared_kernel.domain.models.retention_period import RetentionPeriod
from emerald.shared_kernel.domain.models.soft_deletable import SoftDeletableMixin

_MAX_PASSWORD_HISTORY = 5


class User(SoftDeletableMixin, AuditableMixin, AggregateRoot):
    """User aggregate root — the central identity entity for IAM."""

    def __init__(
        self,
        *,
        email: EmailAddress,
        username: Username,
        password: HashedPassword | None = None,
        password_history: list[str] | None = None,
        auth_providers: set[AuthProvider] | None = None,
        status: UserStatus = UserStatus.PENDING_VERIFICATION,
        email_verified: bool = False,
        preferences: UserPreferences | None = None,
        full_name: str | None = None,
        last_login_at: datetime | None = None,
        suspension_reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.email = email
        self.username = username
        self.full_name = full_name
        self.password = password
        self.password_history: list[str] = password_history if password_history is not None else []
        self.auth_providers: set[AuthProvider] = (
            auth_providers if auth_providers is not None else set()
        )
        self.status = status
        self.email_verified = email_verified
        self.preferences = preferences if preferences is not None else UserPreferences()
        self.last_login_at = last_login_at
        self.suspension_reason = suspension_reason

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def register(
        cls,
        email: EmailAddress,
        username: Username,
        hashed_password: HashedPassword,
    ) -> User:
        """Create a new user via password registration."""
        user_id = uuid.uuid4()
        now = datetime.now(UTC)
        provider = AuthProvider(ProviderType.PASSWORD, None, now)
        user = cls(
            email=email,
            username=username,
            password=hashed_password,
            auth_providers={provider},
            status=UserStatus.PENDING_VERIFICATION,
            email_verified=False,
            password_history=[],
            preferences=UserPreferences(),
            id=user_id,
            created_by=user_id,
        )
        user._register_event(
            UserRegistered(
                aggregate_id=user.id,
                email=str(email),
                username=str(username),
            )
        )
        return user

    # -- Email Verification ----------------------------------------------------

    def verify_email(self) -> None:
        """Verify email: PENDING_VERIFICATION -> ACTIVE."""
        self._require_status(UserStatus.PENDING_VERIFICATION, "verify_email")
        self.status = UserStatus.ACTIVE
        self.email_verified = True
        self._touch()
        self._register_event(EmailVerified(aggregate_id=self.id))

    # -- Profile Updates -------------------------------------------------------

    def update_email(self, new_email: EmailAddress) -> None:
        """Change email — triggers re-verification."""
        self._require_status(UserStatus.ACTIVE, "update_email")
        old_email = str(self.email)
        self.email = new_email
        self.email_verified = False
        self.status = UserStatus.PENDING_VERIFICATION
        self._touch()
        self._register_event(
            UserEmailChanged(
                aggregate_id=self.id,
                old_email=old_email,
                new_email=str(new_email),
            )
        )

    def update_username(self, new_username: Username) -> None:
        """Change username."""
        self._require_status(UserStatus.ACTIVE, "update_username")
        old_username = str(self.username)
        self.username = new_username
        self._touch()
        self._register_event(
            UserUsernameChanged(
                aggregate_id=self.id,
                old_username=old_username,
                new_username=str(new_username),
            )
        )

    def update_full_name(self, name: str | None) -> None:
        """Change or clear full name."""
        self._require_status(UserStatus.ACTIVE, "update_full_name")
        self.full_name = name
        self._touch()

    def update_preferences(self, preferences: UserPreferences) -> None:
        """Update display settings."""
        self._require_status(UserStatus.ACTIVE, "update_preferences")
        self.preferences = preferences
        self._touch()

    # -- Password Management ---------------------------------------------------

    def change_password(self, new_hashed: HashedPassword, old_hash_to_archive: str) -> None:
        """Change password, archiving the old hash in history."""
        self._require_status(UserStatus.ACTIVE, "change_password")
        self.password_history.append(old_hash_to_archive)
        if len(self.password_history) > _MAX_PASSWORD_HISTORY:
            self.password_history = self.password_history[-_MAX_PASSWORD_HISTORY:]
        self.password = new_hashed
        self._touch()
        self._register_event(PasswordChanged(aggregate_id=self.id))

    def set_initial_password(self, hashed: HashedPassword) -> None:
        """Set password for a social-only user."""
        self._require_status(UserStatus.ACTIVE, "set_initial_password")
        if self.password is not None:
            raise PasswordAlreadySetError("User already has a password")
        self.password = hashed
        now = datetime.now(UTC)
        provider = AuthProvider(ProviderType.PASSWORD, None, now)
        self.auth_providers.add(provider)
        self._touch()
        self._register_event(PasswordChanged(aggregate_id=self.id))

    # -- Auth Provider Management ----------------------------------------------

    def link_auth_provider(self, provider: AuthProvider) -> None:
        """Link an additional auth provider."""
        self._require_status(UserStatus.ACTIVE, "link_auth_provider")
        if provider in self.auth_providers:
            raise ProviderAlreadyLinkedError(
                f"Provider {provider.provider_type.value} is already linked"
            )
        self.auth_providers.add(provider)
        self._touch()
        self._register_event(
            AuthProviderLinked(
                aggregate_id=self.id,
                provider_type=provider.provider_type.value,
            )
        )

    def unlink_auth_provider(self, provider_type: ProviderType) -> None:
        """Remove an auth provider."""
        self._require_status(UserStatus.ACTIVE, "unlink_auth_provider")
        target = None
        for p in self.auth_providers:
            if p.provider_type == provider_type:
                target = p
                break
        if target is None:
            raise ProviderNotLinkedError(f"Provider {provider_type.value} is not linked")
        if len(self.auth_providers) <= 1:
            raise CannotUnlinkLastProviderError("Cannot unlink the last remaining auth provider")
        self.auth_providers.discard(target)
        if provider_type == ProviderType.PASSWORD:
            self.password = None
            self.password_history = []
        self._touch()
        self._register_event(
            AuthProviderUnlinked(
                aggregate_id=self.id,
                provider_type=provider_type.value,
            )
        )

    # -- Lifecycle State Machine -----------------------------------------------

    def suspend(self, reason: str | None = None) -> None:
        """ACTIVE -> SUSPENDED."""
        self._require_status(UserStatus.ACTIVE, "suspend")
        self.status = UserStatus.SUSPENDED
        self.suspension_reason = reason
        self._touch()
        self._register_event(UserSuspended(aggregate_id=self.id, reason=reason))

    def unsuspend(self) -> None:
        """SUSPENDED -> ACTIVE."""
        self._require_status(UserStatus.SUSPENDED, "unsuspend")
        self.status = UserStatus.ACTIVE
        self.suspension_reason = None
        self._touch()
        self._register_event(UserUnsuspended(aggregate_id=self.id))

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """ACTIVE or SUSPENDED -> DELETED."""
        if self.status not in (UserStatus.ACTIVE, UserStatus.SUSPENDED):
            raise InvalidStateTransitionError(f"Cannot soft_delete from {self.status.value}")
        # Delegate to SoftDeletableMixin for timestamp/retention handling
        super().soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
        self.status = UserStatus.DELETED
        self.suspension_reason = None
        self._touch()
        self._register_event(UserSoftDeleted(aggregate_id=self.id, deleted_by=deleted_by))

    def recover(self) -> None:
        """DELETED -> ACTIVE."""
        self._require_status(UserStatus.DELETED, "recover")
        super().recover()
        self.status = UserStatus.ACTIVE
        self.email_verified = True
        self._touch()
        self._register_event(UserRecovered(aggregate_id=self.id))

    # -- Login Recording -------------------------------------------------------

    def record_login(self) -> None:
        """Record a successful login."""
        self._require_status(UserStatus.ACTIVE, "record_login")
        self.last_login_at = datetime.now(UTC)
        self._touch()
        self._register_event(UserLoggedIn(aggregate_id=self.id))

    # -- Private Helpers -------------------------------------------------------

    def _require_status(self, required: UserStatus, action: str) -> None:
        """Guard clause for state-dependent operations."""
        if self.status != required:
            raise InvalidStateTransitionError(
                f"Cannot {action} from {self.status.value} (requires {required.value})"
            )

    def _touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)

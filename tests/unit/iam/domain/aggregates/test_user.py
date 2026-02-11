import uuid
from datetime import UTC, datetime

import pytest

from emerald.iam.domain.events import (
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
    AccountSuspendedError,
    AuthenticationFailedError,
    CannotUnlinkLastProviderError,
    EmailNotVerifiedError,
    InvalidStateTransitionError,
    PasswordAlreadySetError,
    ProviderAlreadyLinkedError,
    ProviderNotLinkedError,
)
from emerald.iam.domain.models import (
    AuthProvider,
    EmailAddress,
    HashedPassword,
    ProviderType,
    User,
    Username,
    UserPreferences,
    UserStatus,
)
from emerald.shared_kernel.domain.models import RetentionPeriod, RetentionUnit


def _make_user(**overrides) -> User:
    """Create a registered user for testing."""
    user = User.register(
        email=overrides.pop("email", EmailAddress("test@example.com")),
        username=overrides.pop("username", Username("testuser")),
        hashed_password=overrides.pop("hashed_password", HashedPassword("hashed:password123")),
    )
    user.collect_events()  # clear registration event
    return user


def _make_active_user(**overrides) -> User:
    """Create a verified, active user."""
    user = _make_user(**overrides)
    user.verify_email()
    user.collect_events()  # clear verification event
    return user


# -- Registration --------------------------------------------------------------


class TestUserRegistration:
    def test_register_returns_user(self):
        user = User.register(
            email=EmailAddress("a@b.com"),
            username=Username("johndoe"),
            hashed_password=HashedPassword("hash123"),
        )
        assert isinstance(user, User)

    def test_register_status_pending(self):
        user = _make_user()
        assert user.status == UserStatus.PENDING_VERIFICATION

    def test_register_email_not_verified(self):
        user = _make_user()
        assert user.email_verified is False

    def test_register_password_history_empty(self):
        user = _make_user()
        assert user.password_history == []

    def test_register_has_password_provider(self):
        user = _make_user()
        types = {p.provider_type for p in user.auth_providers}
        assert types == {ProviderType.PASSWORD}

    def test_register_default_preferences(self):
        user = _make_user()
        assert user.preferences == UserPreferences()

    def test_register_created_by_is_own_id(self):
        user = _make_user()
        assert user.created_by == user.id

    def test_register_emits_user_registered_event(self):
        user = User.register(
            email=EmailAddress("a@b.com"),
            username=Username("johndoe"),
            hashed_password=HashedPassword("hash123"),
        )
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRegistered)
        assert events[0].email == "a@b.com"
        assert events[0].username == "johndoe"

    def test_register_identity_equality(self):
        user = _make_user()
        assert user == user

    def test_register_full_name_is_none(self):
        user = _make_user()
        assert user.full_name is None

    def test_register_last_login_is_none(self):
        user = _make_user()
        assert user.last_login_at is None


# -- Email Verification -------------------------------------------------------


class TestEmailVerification:
    def test_verify_from_pending(self):
        user = _make_user()
        user.verify_email()
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is True

    def test_verify_emits_event(self):
        user = _make_user()
        user.verify_email()
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], EmailVerified)

    def test_verify_from_active_raises(self):
        user = _make_active_user()
        with pytest.raises(InvalidStateTransitionError):
            user.verify_email()

    def test_verify_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.verify_email()

    def test_verify_from_deleted_raises(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.verify_email()


# -- Profile Updates -----------------------------------------------------------


class TestProfileUpdates:
    def test_update_email_resets_verification(self):
        user = _make_active_user()
        user.update_email(EmailAddress("new@example.com"))
        assert user.email_verified is False
        assert user.status == UserStatus.PENDING_VERIFICATION
        assert str(user.email) == "new@example.com"

    def test_update_email_emits_event(self):
        user = _make_active_user()
        user.update_email(EmailAddress("new@example.com"))
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserEmailChanged)
        assert events[0].old_email == "test@example.com"
        assert events[0].new_email == "new@example.com"

    def test_update_email_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.update_email(EmailAddress("new@example.com"))

    def test_update_email_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.update_email(EmailAddress("new@example.com"))

    def test_update_email_from_deleted_raises(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.update_email(EmailAddress("new@example.com"))

    def test_update_username(self):
        user = _make_active_user()
        user.update_username(Username("newname"))
        assert str(user.username) == "newname"

    def test_update_username_emits_event(self):
        user = _make_active_user()
        user.update_username(Username("newname"))
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserUsernameChanged)
        assert events[0].old_username == "testuser"
        assert events[0].new_username == "newname"

    def test_update_username_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.update_username(Username("newname"))

    def test_update_full_name(self):
        user = _make_active_user()
        user.update_full_name("John Doe")
        assert user.full_name == "John Doe"

    def test_update_full_name_clear(self):
        user = _make_active_user()
        user.update_full_name("John Doe")
        user.update_full_name(None)
        assert user.full_name is None

    def test_update_full_name_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.update_full_name("name")

    def test_update_preferences(self):
        user = _make_active_user()
        from emerald.shared_kernel.domain.models import Currency

        prefs = UserPreferences(
            timezone="America/New_York", locale="es-MX", display_currency=Currency.EUR
        )
        user.update_preferences(prefs)
        assert user.preferences == prefs

    def test_update_preferences_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.update_preferences(UserPreferences())


# -- Password Management -------------------------------------------------------


class TestPasswordManagement:
    def test_change_password(self):
        user = _make_active_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        user.change_password(HashedPassword("new_hash"), old_hash)
        assert user.password == HashedPassword("new_hash")
        assert old_hash in user.password_history

    def test_change_password_emits_event(self):
        user = _make_active_user()
        user.change_password(HashedPassword("new_hash"), "old_hash")
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], PasswordChanged)

    def test_change_password_trims_history_to_5(self):
        user = _make_active_user()
        for i in range(6):
            assert user.password is not None
            old_hash = user.password.hashed_value
            user.change_password(HashedPassword(f"hash_{i}"), old_hash)
        assert len(user.password_history) == 5

    def test_change_password_fifo_order(self):
        user = _make_active_user()
        for i in range(7):
            assert user.password is not None
            old_hash = user.password.hashed_value
            user.change_password(HashedPassword(f"hash_{i}"), old_hash)
        # oldest entries should have been evicted
        assert user.password_history[0] != "hashed:password123"

    def test_change_password_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.change_password(HashedPassword("new"), "old")

    def test_change_password_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.change_password(HashedPassword("new"), "old")

    def test_set_initial_password_on_social_user(self):
        user = _make_active_user()
        # Simulate social-only user: unlink PASSWORD after adding GOOGLE
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        user.unlink_auth_provider(ProviderType.PASSWORD)
        user.collect_events()
        assert user.password is None

        user.set_initial_password(HashedPassword("new_hash"))
        assert user.password == HashedPassword("new_hash")
        types = {p.provider_type for p in user.auth_providers}
        assert ProviderType.PASSWORD in types

    def test_set_initial_password_emits_event(self):
        user = _make_active_user()
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        user.unlink_auth_provider(ProviderType.PASSWORD)
        user.collect_events()

        user.set_initial_password(HashedPassword("new_hash"))
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], PasswordChanged)

    def test_set_initial_password_when_exists_raises(self):
        user = _make_active_user()
        with pytest.raises(PasswordAlreadySetError):
            user.set_initial_password(HashedPassword("another"))

    def test_set_initial_password_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.set_initial_password(HashedPassword("new"))


# -- Auth Provider Management --------------------------------------------------


class TestAuthProviderManagement:
    def test_link_new_provider(self):
        user = _make_active_user()
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        types = {p.provider_type for p in user.auth_providers}
        assert ProviderType.GOOGLE in types

    def test_link_emits_event(self):
        user = _make_active_user()
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], AuthProviderLinked)
        assert events[0].provider_type == "GOOGLE"

    def test_link_duplicate_raises(self):
        user = _make_active_user()
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        user.collect_events()
        with pytest.raises(ProviderAlreadyLinkedError):
            user.link_auth_provider(AuthProvider(ProviderType.GOOGLE, "g-456", now))

    def test_link_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        now = datetime.now(UTC)
        with pytest.raises(InvalidStateTransitionError):
            user.link_auth_provider(AuthProvider(ProviderType.GOOGLE, "g-123", now))

    def test_unlink_provider(self):
        user = _make_active_user()
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        user.collect_events()

        user.unlink_auth_provider(ProviderType.GOOGLE)
        types = {p.provider_type for p in user.auth_providers}
        assert ProviderType.GOOGLE not in types

    def test_unlink_emits_event(self):
        user = _make_active_user()
        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        user.collect_events()

        user.unlink_auth_provider(ProviderType.GOOGLE)
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], AuthProviderUnlinked)
        assert events[0].provider_type == "GOOGLE"

    def test_unlink_last_provider_raises(self):
        user = _make_active_user()
        with pytest.raises(CannotUnlinkLastProviderError):
            user.unlink_auth_provider(ProviderType.PASSWORD)

    def test_unlink_not_linked_raises(self):
        user = _make_active_user()
        with pytest.raises(ProviderNotLinkedError):
            user.unlink_auth_provider(ProviderType.GOOGLE)

    def test_unlink_password_clears_password_and_history(self):
        user = _make_active_user()
        user.change_password(HashedPassword("new_hash"), "old_hash")
        user.collect_events()

        now = datetime.now(UTC)
        google = AuthProvider(ProviderType.GOOGLE, "g-123", now)
        user.link_auth_provider(google)
        user.collect_events()

        user.unlink_auth_provider(ProviderType.PASSWORD)
        assert user.password is None
        assert user.password_history == []

    def test_unlink_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.unlink_auth_provider(ProviderType.PASSWORD)


# -- Lifecycle State Machine ---------------------------------------------------


class TestLifecycleStateMachine:
    # -- suspend --
    def test_suspend_from_active(self):
        user = _make_active_user()
        user.suspend("Policy violation")
        assert user.status == UserStatus.SUSPENDED
        assert user.suspension_reason == "Policy violation"

    def test_suspend_emits_event(self):
        user = _make_active_user()
        user.suspend("reason")
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserSuspended)
        assert events[0].reason == "reason"

    def test_suspend_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.suspend()

    def test_suspend_from_deleted_raises(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.suspend()

    # -- unsuspend --
    def test_unsuspend_from_suspended(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        user.unsuspend()
        assert user.status == UserStatus.ACTIVE
        assert user.suspension_reason is None

    def test_unsuspend_emits_event(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        user.unsuspend()
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserUnsuspended)

    def test_unsuspend_from_active_raises(self):
        user = _make_active_user()
        with pytest.raises(InvalidStateTransitionError):
            user.unsuspend()

    def test_unsuspend_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.unsuspend()

    # -- soft_delete --
    def test_soft_delete_from_active(self):
        user = _make_active_user()
        admin_id = uuid.uuid4()
        user.soft_delete(admin_id, RetentionPeriod(90, RetentionUnit.DAYS), "Requested")
        assert user.status == UserStatus.DELETED
        assert user.deleted_at is not None
        assert user.deleted_by == admin_id
        assert user.deletion_reason == "Requested"
        assert user.hard_delete_scheduled_at is not None

    def test_soft_delete_from_suspended(self):
        user = _make_active_user()
        user.suspend("Policy")
        user.collect_events()
        admin_id = uuid.uuid4()
        user.soft_delete(admin_id, RetentionPeriod(90, RetentionUnit.DAYS))
        assert user.status == UserStatus.DELETED

    def test_soft_delete_emits_event(self):
        user = _make_active_user()
        admin_id = uuid.uuid4()
        user.soft_delete(admin_id, RetentionPeriod(90, RetentionUnit.DAYS))
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserSoftDeleted)
        assert events[0].deleted_by == admin_id

    def test_soft_delete_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))

    def test_soft_delete_from_deleted_raises(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))

    # -- recover --
    def test_recover_from_deleted(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        user.recover()
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is True
        assert user.deleted_at is None
        assert user.deleted_by is None
        assert user.hard_delete_scheduled_at is None

    def test_recover_emits_event(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        user.recover()
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRecovered)

    def test_recover_from_active_raises(self):
        user = _make_active_user()
        with pytest.raises(InvalidStateTransitionError):
            user.recover()

    def test_recover_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.recover()

    def test_recover_previously_suspended_goes_to_active(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        user.recover()
        assert user.status == UserStatus.ACTIVE


# -- Login Recording -----------------------------------------------------------


class TestLoginRecording:
    def test_record_login_sets_timestamp(self):
        user = _make_active_user()
        assert user.last_login_at is None
        user.record_login()
        assert user.last_login_at is not None
        assert user.last_login_at.tzinfo is not None

    def test_record_login_emits_event(self):
        user = _make_active_user()
        user.record_login()
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserLoggedIn)

    def test_record_login_from_pending_raises(self):
        user = _make_user()
        with pytest.raises(InvalidStateTransitionError):
            user.record_login()

    def test_record_login_from_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.record_login()

    def test_record_login_from_deleted_raises(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(InvalidStateTransitionError):
            user.record_login()


# -- Authentication Validation Guards ------------------------------------------


class TestUserAuthenticationValidation:
    def test_validate_can_authenticate_active_passes(self):
        user = _make_active_user()
        user.validate_can_authenticate()  # should not raise

    def test_validate_can_authenticate_pending_raises_email_not_verified(self):
        user = _make_user()
        with pytest.raises(EmailNotVerifiedError):
            user.validate_can_authenticate()

    def test_validate_can_authenticate_suspended_raises_account_suspended(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(AccountSuspendedError):
            user.validate_can_authenticate()

    def test_validate_can_authenticate_deleted_raises_authentication_failed(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(AuthenticationFailedError):
            user.validate_can_authenticate()

    def test_validate_can_social_login_active_passes(self):
        user = _make_active_user()
        user.validate_can_social_login()  # should not raise

    def test_validate_can_social_login_pending_passes(self):
        user = _make_user()
        user.validate_can_social_login()  # PENDING is allowed for social

    def test_validate_can_social_login_suspended_raises(self):
        user = _make_active_user()
        user.suspend()
        user.collect_events()
        with pytest.raises(AccountSuspendedError):
            user.validate_can_social_login()

    def test_validate_can_social_login_deleted_raises(self):
        user = _make_active_user()
        user.soft_delete(uuid.uuid4(), RetentionPeriod(90, RetentionUnit.DAYS))
        user.collect_events()
        with pytest.raises(AuthenticationFailedError):
            user.validate_can_social_login()

    def test_validate_can_link_provider_active_passes(self):
        user = _make_active_user()
        user.validate_can_link_provider()  # should not raise

    def test_validate_can_link_provider_non_active_raises(self):
        user = _make_user()  # PENDING_VERIFICATION
        with pytest.raises(AuthenticationFailedError):
            user.validate_can_link_provider()

    def test_validate_can_set_username_active_passes(self):
        user = _make_active_user()
        user.validate_can_set_username()  # should not raise

    def test_validate_can_set_username_non_active_raises(self):
        user = _make_user()  # PENDING_VERIFICATION
        with pytest.raises(AuthenticationFailedError):
            user.validate_can_set_username()


# -- Version Control -----------------------------------------------------------


class TestUserVersionControl:
    def test_register_factory_creates_user_at_version_zero(self):
        user = User.register(
            email=EmailAddress("a@b.com"),
            username=Username("testuser"),
            hashed_password=HashedPassword("hash123"),
        )
        assert user.version == 0

    def test_verify_email_increments_version(self):
        user = _make_user()
        assert user.version == 0
        user.verify_email()
        assert user.version == 1

    def test_multiple_mutations_increment_version_each_time(self):
        user = _make_active_user()  # verify_email already bumped to 1
        initial_version = user.version
        user.update_full_name("Alice")
        assert user.version == initial_version + 1
        user.update_full_name("Bob")
        assert user.version == initial_version + 2

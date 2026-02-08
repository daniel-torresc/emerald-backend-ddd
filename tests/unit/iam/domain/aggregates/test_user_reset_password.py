import uuid

import pytest

from emerald.iam.domain.events import PasswordChanged
from emerald.iam.domain.exceptions import InvalidStateTransitionError
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.hashed_password import HashedPassword
from emerald.iam.domain.models.user import User
from emerald.iam.domain.models.username import Username
from emerald.shared_kernel.domain.models.retention_period import RetentionPeriod, RetentionUnit


def _make_pending_user() -> User:
    """Create a PENDING_VERIFICATION user."""
    user = User.register(
        email=EmailAddress("test@example.com"),
        username=Username("testuser"),
        hashed_password=HashedPassword("hashed:password"),
    )
    user.collect_events()
    return user


def _make_active_user() -> User:
    """Create an ACTIVE user (registered + email verified)."""
    user = _make_pending_user()
    user.verify_email()
    user.collect_events()
    return user


def _make_suspended_user() -> User:
    """Create a SUSPENDED user."""
    user = _make_active_user()
    user.suspend("test reason")
    user.collect_events()
    return user


def _make_deleted_user() -> User:
    """Create a DELETED user."""
    user = _make_active_user()
    user.soft_delete(
        deleted_by=uuid.uuid4(),
        retention=RetentionPeriod(30, RetentionUnit.DAYS),
    )
    user.collect_events()
    return user


class TestResetPasswordFromActive:
    def test_succeeds(self):
        user = _make_active_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        user.reset_password(HashedPassword("hashed:new_password"), old_hash)
        assert user.password == HashedPassword("hashed:new_password")

    def test_emits_password_changed_event(self):
        user = _make_active_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        user.reset_password(HashedPassword("hashed:new_password"), old_hash)
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], PasswordChanged)


class TestResetPasswordFromSuspended:
    def test_succeeds(self):
        user = _make_suspended_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        user.reset_password(HashedPassword("hashed:new_password"), old_hash)
        assert user.password == HashedPassword("hashed:new_password")

    def test_emits_password_changed_event(self):
        user = _make_suspended_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        user.reset_password(HashedPassword("hashed:new_password"), old_hash)
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], PasswordChanged)


class TestResetPasswordFromInvalidStates:
    def test_raises_from_pending_verification(self):
        user = _make_pending_user()
        with pytest.raises(InvalidStateTransitionError):
            user.reset_password(HashedPassword("hashed:new_password"), "old_hash")

    def test_raises_from_deleted(self):
        user = _make_deleted_user()
        with pytest.raises(InvalidStateTransitionError):
            user.reset_password(HashedPassword("hashed:new_password"), "old_hash")


class TestResetPasswordHistoryArchival:
    def test_archives_old_password_hash(self):
        user = _make_active_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        user.reset_password(HashedPassword("hashed:new_password"), old_hash)
        assert old_hash in user.password_history

    def test_history_max_five_fifo(self):
        user = _make_active_user()
        # Reset password 6 times to exceed max history of 5
        for i in range(6):
            assert user.password is not None
            old_hash = user.password.hashed_value
            user.reset_password(HashedPassword(f"hashed:pw_{i}"), old_hash)
            user.collect_events()
        assert len(user.password_history) == 5
        # The very first archived hash should have been evicted
        assert "hashed:password" not in user.password_history

    def test_sets_new_password(self):
        user = _make_active_user()
        assert user.password is not None
        old_hash = user.password.hashed_value
        new_pw = HashedPassword("hashed:brand_new")
        user.reset_password(new_pw, old_hash)
        assert user.password == new_pw

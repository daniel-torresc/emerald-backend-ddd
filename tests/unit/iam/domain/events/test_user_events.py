import uuid

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
from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_ALL_EVENTS = [
    UserRegistered,
    EmailVerified,
    UserEmailChanged,
    UserUsernameChanged,
    PasswordChanged,
    AuthProviderLinked,
    AuthProviderUnlinked,
    UserSuspended,
    UserUnsuspended,
    UserSoftDeleted,
    UserRecovered,
    UserLoggedIn,
]


class TestUserEventsBase:
    @pytest.mark.parametrize("event_cls", _ALL_EVENTS)
    def test_extends_domain_event(self, event_cls):
        assert issubclass(event_cls, DomainEvent)

    @pytest.mark.parametrize("event_cls", _ALL_EVENTS)
    def test_aggregate_type_is_user(self, event_cls):
        event = event_cls(aggregate_id=uuid.uuid4())
        assert event.aggregate_type == "User"

    @pytest.mark.parametrize("event_cls", _ALL_EVENTS)
    def test_has_event_id_and_occurred_at(self, event_cls):
        event = event_cls(aggregate_id=uuid.uuid4())
        assert isinstance(event.event_id, uuid.UUID)
        assert event.occurred_at is not None

    @pytest.mark.parametrize("event_cls", _ALL_EVENTS)
    def test_immutable(self, event_cls):
        event = event_cls(aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            event.aggregate_type = "Other"


class TestUserRegisteredEvent:
    def test_carries_email_and_username(self):
        uid = uuid.uuid4()
        event = UserRegistered(aggregate_id=uid, email="a@b.com", username="johndoe")
        assert event.email == "a@b.com"
        assert event.username == "johndoe"
        assert event.aggregate_id == uid


class TestUserEmailChangedEvent:
    def test_carries_old_and_new_email(self):
        event = UserEmailChanged(
            aggregate_id=uuid.uuid4(),
            old_email="old@example.com",
            new_email="new@example.com",
        )
        assert event.old_email == "old@example.com"
        assert event.new_email == "new@example.com"


class TestUserUsernameChangedEvent:
    def test_carries_old_and_new_username(self):
        event = UserUsernameChanged(
            aggregate_id=uuid.uuid4(),
            old_username="old_user",
            new_username="new_user",
        )
        assert event.old_username == "old_user"
        assert event.new_username == "new_user"


class TestPasswordChangedEvent:
    def test_no_password_data(self):
        event = PasswordChanged(aggregate_id=uuid.uuid4())
        attrs = vars(event)
        for key, value in attrs.items():
            if isinstance(value, str) and key not in ("aggregate_type",):
                assert "password" not in value.lower()


class TestAuthProviderLinkedEvent:
    def test_carries_provider_type(self):
        event = AuthProviderLinked(aggregate_id=uuid.uuid4(), provider_type="GOOGLE")
        assert event.provider_type == "GOOGLE"


class TestAuthProviderUnlinkedEvent:
    def test_carries_provider_type(self):
        event = AuthProviderUnlinked(aggregate_id=uuid.uuid4(), provider_type="PASSWORD")
        assert event.provider_type == "PASSWORD"


class TestUserSuspendedEvent:
    def test_carries_reason(self):
        event = UserSuspended(aggregate_id=uuid.uuid4(), reason="Policy violation")
        assert event.reason == "Policy violation"

    def test_reason_optional(self):
        event = UserSuspended(aggregate_id=uuid.uuid4())
        assert event.reason is None


class TestUserSoftDeletedEvent:
    def test_carries_deleted_by(self):
        admin_id = uuid.uuid4()
        event = UserSoftDeleted(aggregate_id=uuid.uuid4(), deleted_by=admin_id)
        assert event.deleted_by == admin_id

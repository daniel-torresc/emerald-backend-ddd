import uuid

import pytest

from emerald.iam.domain.events.auth_events import (
    AllSessionsRevoked,
    LoginFailed,
    PasswordResetRequested,
    TokenFamilyCompromised,
    TokenRefreshed,
    TokenRevoked,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_ALL_AUTH_EVENTS = [
    LoginFailed,
    TokenRefreshed,
    TokenRevoked,
    TokenFamilyCompromised,
    AllSessionsRevoked,
    PasswordResetRequested,
]


class TestAuthEventsBase:
    @pytest.mark.parametrize("event_cls", _ALL_AUTH_EVENTS)
    def test_extends_domain_event(self, event_cls):
        assert issubclass(event_cls, DomainEvent)

    @pytest.mark.parametrize("event_cls", _ALL_AUTH_EVENTS)
    def test_aggregate_type_is_user(self, event_cls):
        event = event_cls(aggregate_id=uuid.uuid4())
        assert event.aggregate_type == "User"

    @pytest.mark.parametrize("event_cls", _ALL_AUTH_EVENTS)
    def test_has_event_id_and_occurred_at(self, event_cls):
        event = event_cls(aggregate_id=uuid.uuid4())
        assert isinstance(event.event_id, uuid.UUID)
        assert event.occurred_at is not None

    @pytest.mark.parametrize("event_cls", _ALL_AUTH_EVENTS)
    def test_immutable(self, event_cls):
        event = event_cls(aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            event.aggregate_type = "Other"


class TestLoginFailed:
    def test_carries_email_as_string(self):
        event = LoginFailed(aggregate_id=uuid.UUID(int=0), email="bad@example.com")
        assert event.email == "bad@example.com"
        assert isinstance(event.email, str)

    def test_uses_nil_uuid_as_aggregate_id(self):
        nil = uuid.UUID(int=0)
        event = LoginFailed(aggregate_id=nil, email="bad@example.com")
        assert event.aggregate_id == nil

    def test_no_raw_token_or_password_data(self):
        event = LoginFailed(aggregate_id=uuid.UUID(int=0), email="user@example.com")
        attrs = vars(event)
        for key in attrs:
            assert "password" not in key.lower()
            assert "token" not in key.lower()


class TestTokenRefreshed:
    def test_carries_user_id_and_family_id(self):
        uid = uuid.uuid4()
        fid = uuid.uuid4()
        event = TokenRefreshed(aggregate_id=uid, user_id=uid, family_id=fid)
        assert event.user_id == uid
        assert event.family_id == fid

    def test_no_raw_token_values(self):
        event = TokenRefreshed(aggregate_id=uuid.uuid4())
        attrs = vars(event)
        for key, value in attrs.items():
            if isinstance(value, str):
                assert "token" not in value.lower()


class TestTokenRevoked:
    def test_carries_user_id_and_token_id(self):
        uid = uuid.uuid4()
        tid = uuid.uuid4()
        event = TokenRevoked(aggregate_id=uid, user_id=uid, token_id=tid)
        assert event.user_id == uid
        assert event.token_id == tid

    def test_no_raw_token_values(self):
        event = TokenRevoked(aggregate_id=uuid.uuid4())
        attrs = vars(event)
        for key, value in attrs.items():
            if isinstance(value, str):
                assert "token" not in value.lower()


class TestTokenFamilyCompromised:
    def test_carries_user_id_and_family_id(self):
        uid = uuid.uuid4()
        fid = uuid.uuid4()
        event = TokenFamilyCompromised(aggregate_id=uid, user_id=uid, family_id=fid)
        assert event.user_id == uid
        assert event.family_id == fid


class TestAllSessionsRevoked:
    def test_carries_user_id(self):
        uid = uuid.uuid4()
        event = AllSessionsRevoked(aggregate_id=uid, user_id=uid)
        assert event.user_id == uid


class TestPasswordResetRequested:
    def test_carries_only_user_id(self):
        uid = uuid.uuid4()
        event = PasswordResetRequested(aggregate_id=uid, user_id=uid)
        assert event.user_id == uid

    def test_no_raw_token_or_password_data(self):
        event = PasswordResetRequested(aggregate_id=uuid.uuid4(), user_id=uuid.uuid4())
        attrs = vars(event)
        for key in attrs:
            if key in ("aggregate_type", "aggregate_id", "event_id", "occurred_at", "user_id"):
                continue
            assert "password" not in key.lower()
            assert "token" not in key.lower()

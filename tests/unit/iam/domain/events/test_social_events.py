import uuid

import pytest

from emerald.iam.domain.events.social_events import (
    UserRegisteredViaSocialProvider,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_ALL_SOCIAL_EVENTS = [
    UserRegisteredViaSocialProvider,
]

_REQUIRED_KWARGS: dict[type, dict] = {
    UserRegisteredViaSocialProvider: {"email": "u@example.com", "provider_type": "GOOGLE"},
}


def _make_event(event_cls: type, **overrides):
    kwargs: dict = {"aggregate_id": uuid.uuid4(), **_REQUIRED_KWARGS.get(event_cls, {})}
    kwargs.update(overrides)
    return event_cls(**kwargs)


class TestSocialEventsBase:
    @pytest.mark.parametrize("event_cls", _ALL_SOCIAL_EVENTS)
    def test_extends_domain_event(self, event_cls):
        assert issubclass(event_cls, DomainEvent)

    @pytest.mark.parametrize("event_cls", _ALL_SOCIAL_EVENTS)
    def test_aggregate_type_is_user(self, event_cls):
        event = _make_event(event_cls)
        assert event.aggregate_type == "user"

    @pytest.mark.parametrize("event_cls", _ALL_SOCIAL_EVENTS)
    def test_has_event_id_and_occurred_at(self, event_cls):
        event = _make_event(event_cls)
        assert isinstance(event.event_id, uuid.UUID)
        assert event.occurred_at is not None

    @pytest.mark.parametrize("event_cls", _ALL_SOCIAL_EVENTS)
    def test_immutable(self, event_cls):
        event = _make_event(event_cls)
        with pytest.raises(AttributeError):
            event.aggregate_type = "Other"


class TestUserRegisteredViaSocialProvider:
    def test_carries_email_and_provider_type(self):
        agg_id = uuid.uuid4()
        event = UserRegisteredViaSocialProvider(
            aggregate_id=agg_id,
            email="user@gmail.com",
            provider_type="GOOGLE",
        )
        assert event.aggregate_id == agg_id
        assert event.email == "user@gmail.com"
        assert event.provider_type == "GOOGLE"

    def test_full_name_defaults_to_none(self):
        event = UserRegisteredViaSocialProvider(
            aggregate_id=uuid.uuid4(),
            email="user@gmail.com",
            provider_type="GOOGLE",
        )
        assert event.full_name is None

    def test_full_name_preserved(self):
        event = UserRegisteredViaSocialProvider(
            aggregate_id=uuid.uuid4(),
            email="user@gmail.com",
            provider_type="GOOGLE",
            full_name="Jane Doe",
        )
        assert event.full_name == "Jane Doe"

    def test_aggregate_type_is_user(self):
        event = UserRegisteredViaSocialProvider(
            aggregate_id=uuid.uuid4(),
            email="user@outlook.com",
            provider_type="MICROSOFT",
        )
        assert event.aggregate_type == "user"

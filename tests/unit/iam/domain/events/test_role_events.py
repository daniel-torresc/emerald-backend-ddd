import uuid

import pytest

from emerald.iam.domain.events.role_events import (
    AdminPermissionGranted,
    AdminPermissionRevoked,
    SuperadminProvisioned,
    UserDemotedToUser,
    UserPromotedToAdmin,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_ALL_ROLE_EVENTS = [
    UserPromotedToAdmin,
    UserDemotedToUser,
    AdminPermissionGranted,
    AdminPermissionRevoked,
    SuperadminProvisioned,
]

_REQUIRED_KWARGS: dict[type, dict] = {
    UserPromotedToAdmin: {
        "permissions": frozenset({"FULL_ADMIN"}),
        "promoted_by_id": uuid.uuid4(),
    },
    UserDemotedToUser: {"demoted_by_id": uuid.uuid4()},
    AdminPermissionGranted: {"permission": "FULL_ADMIN", "granted_by_id": uuid.uuid4()},
    AdminPermissionRevoked: {"permission": "FULL_ADMIN", "revoked_by_id": uuid.uuid4()},
}


def _make_event(event_cls: type, **overrides):
    kwargs: dict = {"aggregate_id": uuid.uuid4(), **_REQUIRED_KWARGS.get(event_cls, {})}
    kwargs.update(overrides)
    return event_cls(**kwargs)


class TestRoleEventsBase:
    @pytest.mark.parametrize("event_cls", _ALL_ROLE_EVENTS)
    def test_extends_domain_event(self, event_cls):
        assert issubclass(event_cls, DomainEvent)

    @pytest.mark.parametrize("event_cls", _ALL_ROLE_EVENTS)
    def test_aggregate_type_is_user(self, event_cls):
        event = _make_event(event_cls)
        assert event.aggregate_type == "user"

    @pytest.mark.parametrize("event_cls", _ALL_ROLE_EVENTS)
    def test_immutable(self, event_cls):
        event = _make_event(event_cls)
        with pytest.raises(AttributeError):
            event.aggregate_type = "Other"

    @pytest.mark.parametrize("event_cls", _ALL_ROLE_EVENTS)
    def test_has_event_id_and_occurred_at(self, event_cls):
        event = _make_event(event_cls)
        assert isinstance(event.event_id, uuid.UUID)
        assert event.occurred_at is not None


class TestUserPromotedToAdminEvent:
    def test_carries_permissions_and_promoter(self):
        uid = uuid.uuid4()
        promoter = uuid.uuid4()
        event = UserPromotedToAdmin(
            aggregate_id=uid,
            permissions=frozenset({"MASTER_DATA_ADMIN", "USER_SUPPORT_ADMIN"}),
            promoted_by_id=promoter,
        )
        assert event.aggregate_id == uid
        assert event.promoted_by_id == promoter
        assert event.permissions == frozenset({"MASTER_DATA_ADMIN", "USER_SUPPORT_ADMIN"})

    def test_permissions_stored_as_frozenset_of_str(self):
        event = UserPromotedToAdmin(
            aggregate_id=uuid.uuid4(),
            permissions=frozenset({"FULL_ADMIN"}),
            promoted_by_id=uuid.uuid4(),
        )
        assert isinstance(event.permissions, frozenset)
        for perm in event.permissions:
            assert isinstance(perm, str)


class TestUserDemotedToUserEvent:
    def test_carries_demoter_id(self):
        uid = uuid.uuid4()
        demoter = uuid.uuid4()
        event = UserDemotedToUser(aggregate_id=uid, demoted_by_id=demoter)
        assert event.aggregate_id == uid
        assert event.demoted_by_id == demoter


class TestAdminPermissionGrantedEvent:
    def test_carries_permission_and_granter(self):
        uid = uuid.uuid4()
        granter = uuid.uuid4()
        event = AdminPermissionGranted(
            aggregate_id=uid,
            permission="COMPLIANCE_ADMIN",
            granted_by_id=granter,
        )
        assert event.permission == "COMPLIANCE_ADMIN"
        assert event.granted_by_id == granter


class TestAdminPermissionRevokedEvent:
    def test_carries_permission_and_revoker(self):
        uid = uuid.uuid4()
        revoker = uuid.uuid4()
        event = AdminPermissionRevoked(
            aggregate_id=uid,
            permission="USER_SUPPORT_ADMIN",
            revoked_by_id=revoker,
        )
        assert event.permission == "USER_SUPPORT_ADMIN"
        assert event.revoked_by_id == revoker

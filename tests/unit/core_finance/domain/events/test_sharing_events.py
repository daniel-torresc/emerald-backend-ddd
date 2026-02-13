import uuid

from emerald.core_finance.domain.events.sharing_events import (
    AccountOwnershipTransferred,
    AccountShared,
    AccountShareLeft,
    AccountShareRevoked,
    AccountShareUpdated,
)


class TestAccountShared:
    def test_aggregate_type(self) -> None:
        assert AccountShared.aggregate_type == "account"

    def test_stores_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        gid = uuid.uuid4()
        event = AccountShared(
            aggregate_id=aid, user_id=uid, permission_level="EDITOR", granted_by=gid
        )
        assert event.aggregate_id == aid
        assert event.user_id == uid
        assert event.permission_level == "EDITOR"
        assert event.granted_by == gid

    def test_auto_event_id(self) -> None:
        event = AccountShared(aggregate_id=uuid.uuid4())
        assert event.event_id is not None

    def test_auto_occurred_at(self) -> None:
        event = AccountShared(aggregate_id=uuid.uuid4())
        assert event.occurred_at is not None


class TestAccountShareUpdated:
    def test_aggregate_type(self) -> None:
        assert AccountShareUpdated.aggregate_type == "account"

    def test_stores_fields(self) -> None:
        event = AccountShareUpdated(
            aggregate_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            old_permission="VIEWER",
            new_permission="EDITOR",
            updated_by=uuid.uuid4(),
        )
        assert event.old_permission == "VIEWER"
        assert event.new_permission == "EDITOR"


class TestAccountShareRevoked:
    def test_aggregate_type(self) -> None:
        assert AccountShareRevoked.aggregate_type == "account"

    def test_stores_fields(self) -> None:
        uid = uuid.uuid4()
        rid = uuid.uuid4()
        event = AccountShareRevoked(aggregate_id=uuid.uuid4(), user_id=uid, revoked_by=rid)
        assert event.user_id == uid
        assert event.revoked_by == rid


class TestAccountShareLeft:
    def test_aggregate_type(self) -> None:
        assert AccountShareLeft.aggregate_type == "account"

    def test_stores_fields(self) -> None:
        uid = uuid.uuid4()
        event = AccountShareLeft(aggregate_id=uuid.uuid4(), user_id=uid)
        assert event.user_id == uid


class TestAccountOwnershipTransferred:
    def test_aggregate_type(self) -> None:
        assert AccountOwnershipTransferred.aggregate_type == "account"

    def test_stores_fields(self) -> None:
        old = uuid.uuid4()
        new = uuid.uuid4()
        event = AccountOwnershipTransferred(
            aggregate_id=uuid.uuid4(), old_owner_id=old, new_owner_id=new
        )
        assert event.old_owner_id == old
        assert event.new_owner_id == new

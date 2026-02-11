import uuid

import pytest

from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.models import RetentionPeriod, RetentionUnit
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin


class _SoftDeletableEntity(SoftDeletableMixin):
    """Test helper that uses SoftDeletableMixin."""

    pass


class TestSoftDelete:
    def test_soft_delete_sets_fields(self) -> None:
        e = _SoftDeletableEntity()
        actor = uuid.uuid4()
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        e.soft_delete(deleted_by=actor, retention=retention)
        assert e.deleted_at is not None
        assert e.deleted_by == actor
        assert e.hard_delete_scheduled_at is not None
        assert e.is_deleted()
        assert not e.is_active()

    def test_soft_delete_with_reason(self) -> None:
        e = _SoftDeletableEntity()
        actor = uuid.uuid4()
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        e.soft_delete(deleted_by=actor, retention=retention, reason="User requested")
        assert e.deletion_reason == "User requested"

    def test_soft_delete_already_deleted_raises(self) -> None:
        e = _SoftDeletableEntity()
        actor = uuid.uuid4()
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        e.soft_delete(deleted_by=actor, retention=retention)
        with pytest.raises(AlreadyDeletedError):
            e.soft_delete(deleted_by=actor, retention=retention)

    def test_hard_delete_scheduled_at_is_calendar_accurate(self) -> None:
        e = _SoftDeletableEntity()
        actor = uuid.uuid4()
        retention = RetentionPeriod(1, RetentionUnit.MONTHS)
        e.soft_delete(deleted_by=actor, retention=retention)
        assert e.hard_delete_scheduled_at is not None
        assert e.deleted_at is not None
        # The scheduled time should be ~1 month after deleted_at
        delta = e.hard_delete_scheduled_at - e.deleted_at
        assert 27 <= delta.days <= 31

    def test_timestamps_are_utc(self) -> None:
        e = _SoftDeletableEntity()
        actor = uuid.uuid4()
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        e.soft_delete(deleted_by=actor, retention=retention)
        assert e.deleted_at is not None
        assert e.deleted_at.tzinfo is not None
        assert e.hard_delete_scheduled_at is not None
        assert e.hard_delete_scheduled_at.tzinfo is not None


class TestRecover:
    def test_recover_clears_all_fields(self) -> None:
        e = _SoftDeletableEntity()
        actor = uuid.uuid4()
        retention = RetentionPeriod(30, RetentionUnit.DAYS)
        e.soft_delete(deleted_by=actor, retention=retention, reason="test")
        e.recover()
        assert e.deleted_at is None
        assert e.deleted_by is None
        assert e.deletion_reason is None
        assert e.hard_delete_scheduled_at is None
        assert not e.is_deleted()
        assert e.is_active()

    def test_recover_on_active_entity_raises(self) -> None:
        e = _SoftDeletableEntity()
        with pytest.raises(NotDeletedError):
            e.recover()


class TestSoftDeletableState:
    def test_initially_active(self) -> None:
        e = _SoftDeletableEntity()
        assert e.is_active()
        assert not e.is_deleted()

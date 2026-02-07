import time
from datetime import UTC, datetime

import pytest

from emerald.shared_kernel.domain.models.timestamped import TimestampedMixin


class _TimestampedEntity(TimestampedMixin):
    """Test helper that uses TimestampedMixin."""

    pass


class TestTimestampedCreation:
    def test_created_at_set_at_construction(self) -> None:
        e = _TimestampedEntity()
        assert isinstance(e.created_at, datetime)

    def test_updated_at_set_at_construction(self) -> None:
        e = _TimestampedEntity()
        assert isinstance(e.updated_at, datetime)

    def test_created_at_is_utc(self) -> None:
        e = _TimestampedEntity()
        assert e.created_at.tzinfo is not None

    def test_updated_at_is_utc(self) -> None:
        e = _TimestampedEntity()
        assert e.updated_at.tzinfo is not None

    def test_explicit_timestamps(self) -> None:
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        e = _TimestampedEntity(created_at=ts, updated_at=ts)
        assert e.created_at == ts
        assert e.updated_at == ts


class TestTimestampedImmutability:
    def test_created_at_is_immutable(self) -> None:
        e = _TimestampedEntity()
        with pytest.raises(AttributeError):
            e.created_at = datetime.now(UTC)  # type: ignore[misc]


class TestTimestampedTouch:
    def test_touch_updates_updated_at(self) -> None:
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        e = _TimestampedEntity(created_at=ts, updated_at=ts)
        time.sleep(0.001)
        e._touch()
        assert e.updated_at > ts

    def test_touch_does_not_change_created_at(self) -> None:
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        e = _TimestampedEntity(created_at=ts)
        e._touch()
        assert e.created_at == ts

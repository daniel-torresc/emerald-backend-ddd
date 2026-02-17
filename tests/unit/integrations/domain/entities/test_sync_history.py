"""Tests for SyncHistory entity."""

import uuid
from datetime import UTC, datetime

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    SyncAlreadyCompletedError,
)
from emerald.integrations.domain.models.entities.sync_history import SyncHistory
from emerald.integrations.domain.models.value_objects.sync_result import SyncResult
from emerald.integrations.domain.models.value_objects.sync_status import SyncStatus


def _make_sync_result(
    *,
    found: int = 10,
    imported: int = 8,
    duplicate: int = 2,
    staged: int = 0,
) -> SyncResult:
    return SyncResult(
        transactions_found=found,
        transactions_imported=imported,
        transactions_duplicate=duplicate,
        transactions_staged=staged,
    )


class TestSyncHistoryCreate:
    """Tests for SyncHistory.create() factory."""

    def test_create_sets_in_progress_status(self) -> None:
        conn_id = uuid.uuid4()
        history = SyncHistory.create(connection_id=conn_id)
        assert history.status == SyncStatus.IN_PROGRESS

    def test_create_stores_connection_id(self) -> None:
        conn_id = uuid.uuid4()
        history = SyncHistory.create(connection_id=conn_id)
        assert history.connection_id == conn_id

    def test_create_started_at_is_recent(self) -> None:
        before = datetime.now(UTC)
        history = SyncHistory.create(connection_id=uuid.uuid4())
        after = datetime.now(UTC)
        assert before <= history.started_at <= after

    def test_create_completed_at_is_none(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        assert history.completed_at is None

    def test_create_count_fields_default_to_zero(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        assert history.transactions_found == 0
        assert history.transactions_imported == 0
        assert history.transactions_duplicate == 0
        assert history.transactions_staged == 0

    def test_create_error_message_is_none(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        assert history.error_message is None

    def test_create_generates_unique_id(self) -> None:
        h1 = SyncHistory.create(connection_id=uuid.uuid4())
        h2 = SyncHistory.create(connection_id=uuid.uuid4())
        assert h1.id != h2.id


class TestSyncHistoryComplete:
    """Tests for SyncHistory.complete() transitions."""

    def test_complete_with_zero_staged_sets_success(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=5, imported=3, duplicate=2, staged=0)
        history.complete(result)
        assert history.status == SyncStatus.SUCCESS

    def test_complete_with_positive_staged_sets_partial(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=5, imported=2, duplicate=1, staged=2)
        history.complete(result)
        assert history.status == SyncStatus.PARTIAL

    def test_complete_sets_completed_at(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=3, imported=3, duplicate=0, staged=0)
        before = datetime.now(UTC)
        history.complete(result)
        after = datetime.now(UTC)
        assert history.completed_at is not None
        assert before <= history.completed_at <= after

    def test_complete_sets_all_count_fields(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=10, imported=5, duplicate=3, staged=2)
        history.complete(result)
        assert history.transactions_found == 10
        assert history.transactions_imported == 5
        assert history.transactions_duplicate == 3
        assert history.transactions_staged == 2

    def test_complete_when_not_in_progress_raises_sync_already_completed(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=1, imported=1, duplicate=0, staged=0)
        history.complete(result)
        with pytest.raises(SyncAlreadyCompletedError):
            history.complete(result)

    def test_complete_after_fail_raises_sync_already_completed(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        history.fail("connection timeout")
        result = _make_sync_result(found=1, imported=1, duplicate=0, staged=0)
        with pytest.raises(SyncAlreadyCompletedError):
            history.complete(result)


class TestSyncHistoryFail:
    """Tests for SyncHistory.fail() transitions."""

    def test_fail_sets_failed_status(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        history.fail("network error")
        assert history.status == SyncStatus.FAILED

    def test_fail_sets_error_message(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        history.fail("timeout after 30s")
        assert history.error_message == "timeout after 30s"

    def test_fail_sets_completed_at(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        before = datetime.now(UTC)
        history.fail("error")
        after = datetime.now(UTC)
        assert history.completed_at is not None
        assert before <= history.completed_at <= after

    def test_fail_when_not_in_progress_raises_sync_already_completed(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        history.fail("first failure")
        with pytest.raises(SyncAlreadyCompletedError):
            history.fail("second failure")

    def test_fail_after_complete_raises_sync_already_completed(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=1, imported=1, duplicate=0, staged=0)
        history.complete(result)
        with pytest.raises(SyncAlreadyCompletedError):
            history.fail("late error")


class TestSyncHistoryDoubleTransition:
    """Tests for invalid double state transitions."""

    def test_double_complete_raises_error(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=2, imported=2, duplicate=0, staged=0)
        history.complete(result)
        with pytest.raises(SyncAlreadyCompletedError):
            history.complete(result)

    def test_fail_after_complete_raises_error(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        result = _make_sync_result(found=2, imported=2, duplicate=0, staged=0)
        history.complete(result)
        with pytest.raises(SyncAlreadyCompletedError):
            history.fail("too late")

    def test_complete_after_fail_raises_error(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        history.fail("crashed")
        result = _make_sync_result(found=2, imported=2, duplicate=0, staged=0)
        with pytest.raises(SyncAlreadyCompletedError):
            history.complete(result)

    def test_double_fail_raises_error(self) -> None:
        history = SyncHistory.create(connection_id=uuid.uuid4())
        history.fail("first")
        with pytest.raises(SyncAlreadyCompletedError):
            history.fail("second")

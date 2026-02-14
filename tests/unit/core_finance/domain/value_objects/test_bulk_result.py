import uuid

import pytest

from emerald.core_finance.domain.models.value_objects.bulk_result import (
    BulkFailure,
    BulkResult,
    BulkSuccess,
)


class TestBulkSuccess:
    def test_construction(self) -> None:
        entity_id = uuid.uuid4()
        s = BulkSuccess(index=0, entity_id=entity_id)
        assert s.index == 0
        assert s.entity_id == entity_id

    def test_frozen(self) -> None:
        s = BulkSuccess(index=0, entity_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            s.index = 1  # type: ignore[misc]


class TestBulkFailure:
    def test_construction_with_entity_id(self) -> None:
        entity_id = uuid.uuid4()
        f = BulkFailure(index=0, entity_id=entity_id, error_code="CODE", error_message="msg")
        assert f.index == 0
        assert f.entity_id == entity_id
        assert f.error_code == "CODE"
        assert f.error_message == "msg"

    def test_construction_without_entity_id(self) -> None:
        f = BulkFailure(index=1, entity_id=None, error_code="ERR", error_message="failed")
        assert f.entity_id is None

    def test_frozen(self) -> None:
        f = BulkFailure(index=0, entity_id=None, error_code="CODE", error_message="msg")
        with pytest.raises(AttributeError):
            f.index = 1  # type: ignore[misc]


class TestBulkResult:
    def test_valid_all_success(self) -> None:
        s1 = BulkSuccess(index=0, entity_id=uuid.uuid4())
        s2 = BulkSuccess(index=1, entity_id=uuid.uuid4())
        result = BulkResult(
            success_count=2, failure_count=0, total_count=2, successes=(s1, s2), failures=()
        )
        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.total_count == 2
        assert result.is_complete_success is True
        assert result.is_complete_failure is False
        assert result.has_failures is False

    def test_valid_all_failure(self) -> None:
        f1 = BulkFailure(index=0, entity_id=None, error_code="E1", error_message="err1")
        f2 = BulkFailure(index=1, entity_id=None, error_code="E2", error_message="err2")
        result = BulkResult(
            success_count=0, failure_count=2, total_count=2, successes=(), failures=(f1, f2)
        )
        assert result.is_complete_success is False
        assert result.is_complete_failure is True
        assert result.has_failures is True

    def test_valid_mixed(self) -> None:
        s = BulkSuccess(index=0, entity_id=uuid.uuid4())
        f = BulkFailure(index=1, entity_id=None, error_code="E", error_message="err")
        result = BulkResult(
            success_count=1, failure_count=1, total_count=2, successes=(s,), failures=(f,)
        )
        assert result.is_complete_success is False
        assert result.is_complete_failure is False
        assert result.has_failures is True

    def test_negative_success_count_raises(self) -> None:
        with pytest.raises(ValueError, match="success_count must be non-negative"):
            BulkResult(success_count=-1, failure_count=0, total_count=-1)

    def test_negative_failure_count_raises(self) -> None:
        with pytest.raises(ValueError, match="failure_count must be non-negative"):
            BulkResult(success_count=0, failure_count=-1, total_count=-1)

    def test_total_count_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="total_count must equal"):
            BulkResult(success_count=1, failure_count=1, total_count=3)

    def test_successes_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="len\\(successes\\) must equal"):
            BulkResult(success_count=1, failure_count=0, total_count=1, successes=(), failures=())

    def test_failures_length_mismatch_raises(self) -> None:
        s = BulkSuccess(index=0, entity_id=uuid.uuid4())
        with pytest.raises(ValueError, match="len\\(failures\\) must equal"):
            BulkResult(success_count=1, failure_count=1, total_count=2, successes=(s,), failures=())

    def test_frozen(self) -> None:
        result = BulkResult(success_count=0, failure_count=0, total_count=0)
        with pytest.raises(AttributeError):
            result.success_count = 1  # type: ignore[misc]

    def test_zero_zero(self) -> None:
        result = BulkResult(success_count=0, failure_count=0, total_count=0)
        assert result.is_complete_success is True
        assert result.is_complete_failure is True
        assert result.has_failures is False

"""Tests for SyncResult value object."""

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidNormalizedTransactionError,
)
from emerald.integrations.domain.models.value_objects.sync_result import SyncResult


class TestSyncResultValid:
    """Valid SyncResult creation scenarios."""

    def test_valid_counts(self) -> None:
        result = SyncResult(
            transactions_found=10,
            transactions_imported=6,
            transactions_duplicate=3,
            transactions_staged=1,
        )
        assert result.transactions_found == 10
        assert result.transactions_imported == 6
        assert result.transactions_duplicate == 3
        assert result.transactions_staged == 1

    def test_all_imported(self) -> None:
        result = SyncResult(
            transactions_found=5,
            transactions_imported=5,
            transactions_duplicate=0,
            transactions_staged=0,
        )
        assert result.transactions_found == 5

    def test_all_duplicate(self) -> None:
        result = SyncResult(
            transactions_found=8,
            transactions_imported=0,
            transactions_duplicate=8,
            transactions_staged=0,
        )
        assert result.transactions_duplicate == 8

    def test_all_staged(self) -> None:
        result = SyncResult(
            transactions_found=3,
            transactions_imported=0,
            transactions_duplicate=0,
            transactions_staged=3,
        )
        assert result.transactions_staged == 3

    def test_all_zero_counts(self) -> None:
        result = SyncResult(
            transactions_found=0,
            transactions_imported=0,
            transactions_duplicate=0,
            transactions_staged=0,
        )
        assert result.transactions_found == 0


class TestSyncResultNegativeCounts:
    """Negative count scenarios."""

    def test_negative_found_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError):
            SyncResult(
                transactions_found=-1,
                transactions_imported=0,
                transactions_duplicate=0,
                transactions_staged=0,
            )

    def test_negative_imported_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError):
            SyncResult(
                transactions_found=0,
                transactions_imported=-1,
                transactions_duplicate=0,
                transactions_staged=0,
            )

    def test_negative_duplicate_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError):
            SyncResult(
                transactions_found=0,
                transactions_imported=0,
                transactions_duplicate=-1,
                transactions_staged=0,
            )

    def test_negative_staged_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError):
            SyncResult(
                transactions_found=0,
                transactions_imported=0,
                transactions_duplicate=0,
                transactions_staged=-1,
            )


class TestSyncResultSumMismatch:
    """Sum mismatch scenarios."""

    def test_sum_exceeds_found_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError, match="must equal found"):
            SyncResult(
                transactions_found=5,
                transactions_imported=3,
                transactions_duplicate=2,
                transactions_staged=1,
            )

    def test_sum_less_than_found_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError, match="must equal found"):
            SyncResult(
                transactions_found=10,
                transactions_imported=3,
                transactions_duplicate=2,
                transactions_staged=1,
            )


class TestSyncResultFrozen:
    """SyncResult is immutable."""

    def test_cannot_set_found(self) -> None:
        result = SyncResult(
            transactions_found=5,
            transactions_imported=3,
            transactions_duplicate=1,
            transactions_staged=1,
        )
        with pytest.raises(AttributeError):
            result.transactions_found = 10  # type: ignore[misc]

    def test_cannot_set_imported(self) -> None:
        result = SyncResult(
            transactions_found=5,
            transactions_imported=3,
            transactions_duplicate=1,
            transactions_staged=1,
        )
        with pytest.raises(AttributeError):
            result.transactions_imported = 0  # type: ignore[misc]

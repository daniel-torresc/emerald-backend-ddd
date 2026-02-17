"""Tests for DeduplicationResult value object."""

import uuid

import pytest

from emerald.integrations.domain.models.value_objects.deduplication_result import (
    DeduplicationResult,
)
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus


class TestDeduplicationResultValid:
    """Valid DeduplicationResult creation scenarios."""

    def test_new_match_status(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.NEW,
            confidence=1.0,
            match_reason="No matching transactions found",
        )
        assert result.match_status == MatchStatus.NEW
        assert result.confidence == 1.0
        assert result.match_reason == "No matching transactions found"
        assert result.matched_transaction_id is None

    def test_duplicate_with_matched_id(self) -> None:
        txn_id = uuid.uuid4()
        result = DeduplicationResult(
            match_status=MatchStatus.DUPLICATE,
            confidence=0.99,
            match_reason="Exact external_id match",
            matched_transaction_id=txn_id,
        )
        assert result.match_status == MatchStatus.DUPLICATE
        assert result.matched_transaction_id == txn_id

    def test_needs_review_status(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.NEEDS_REVIEW,
            confidence=0.75,
            match_reason="Fuzzy amount match within tolerance",
            matched_transaction_id=uuid.uuid4(),
        )
        assert result.match_status == MatchStatus.NEEDS_REVIEW

    def test_user_approved_status(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.USER_APPROVED,
            confidence=0.80,
            match_reason="User approved match",
            matched_transaction_id=uuid.uuid4(),
        )
        assert result.match_status == MatchStatus.USER_APPROVED

    def test_user_rejected_status(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.USER_REJECTED,
            confidence=0.60,
            match_reason="User rejected match",
        )
        assert result.match_status == MatchStatus.USER_REJECTED

    def test_matched_transaction_id_optional(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.NEW,
            confidence=1.0,
            match_reason="Brand new",
        )
        assert result.matched_transaction_id is None


class TestDeduplicationResultFrozen:
    """DeduplicationResult is immutable."""

    def test_cannot_set_match_status(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.NEW,
            confidence=1.0,
            match_reason="New",
        )
        with pytest.raises(AttributeError):
            result.match_status = MatchStatus.DUPLICATE  # type: ignore[misc]

    def test_cannot_set_confidence(self) -> None:
        result = DeduplicationResult(
            match_status=MatchStatus.NEW,
            confidence=1.0,
            match_reason="New",
        )
        with pytest.raises(AttributeError):
            result.confidence = 0.5  # type: ignore[misc]

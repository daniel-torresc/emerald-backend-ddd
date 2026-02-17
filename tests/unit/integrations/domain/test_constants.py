"""Tests for integrations domain constants."""

from decimal import Decimal

from emerald.integrations.domain import constants


class TestSyncFrequencyConstants:
    """Bank connection sync frequency limits."""

    def test_min_sync_frequency_hours(self) -> None:
        assert constants.MIN_SYNC_FREQUENCY_HOURS == 1

    def test_max_sync_frequency_hours(self) -> None:
        assert constants.MAX_SYNC_FREQUENCY_HOURS == 24

    def test_default_sync_frequency_hours(self) -> None:
        assert constants.DEFAULT_SYNC_FREQUENCY_HOURS == 6


class TestFailureThresholdConstants:
    """Failure threshold configuration."""

    def test_max_consecutive_failures(self) -> None:
        assert constants.MAX_CONSECUTIVE_FAILURES == 3


class TestRetryConstants:
    """Retry backoff configuration."""

    def test_retry_base_minutes(self) -> None:
        assert constants.RETRY_BASE_MINUTES == 15

    def test_retry_max_minutes(self) -> None:
        assert constants.RETRY_MAX_MINUTES == 60


class TestProviderConstants:
    """Provider name limits."""

    def test_max_provider_name_length(self) -> None:
        assert constants.MAX_PROVIDER_NAME_LENGTH == 50


class TestNormalizedTransactionConstants:
    """Normalized transaction field limits."""

    def test_max_description_length(self) -> None:
        assert constants.MAX_DESCRIPTION_LENGTH == 500

    def test_max_merchant_length(self) -> None:
        assert constants.MAX_MERCHANT_LENGTH == 200


class TestDeduplicationConstants:
    """Deduplication tolerance."""

    def test_amount_tolerance(self) -> None:
        assert constants.AMOUNT_TOLERANCE == Decimal("0.01")

    def test_amount_tolerance_type(self) -> None:
        assert isinstance(constants.AMOUNT_TOLERANCE, Decimal)

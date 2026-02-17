"""Tests for ProviderName value object."""

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    EmptyProviderNameError,
    ProviderNameTooLongError,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName


class TestProviderNameValid:
    """Valid ProviderName creation scenarios."""

    def test_valid_lowercase(self) -> None:
        name = ProviderName("plaid")
        assert name.value == "plaid"

    def test_trimming_and_lowercasing(self) -> None:
        name = ProviderName("  Plaid  ")
        assert name.value == "plaid"

    def test_mixed_case_normalized(self) -> None:
        name = ProviderName("GoCardless")
        assert name.value == "gocardless"

    def test_exactly_max_length(self) -> None:
        name = ProviderName("a" * 50)
        assert name.value == "a" * 50

    def test_single_character(self) -> None:
        name = ProviderName("x")
        assert name.value == "x"


class TestProviderNameInvalid:
    """Invalid ProviderName creation scenarios."""

    def test_empty_raises_error(self) -> None:
        with pytest.raises(EmptyProviderNameError):
            ProviderName("")

    def test_blank_raises_error(self) -> None:
        with pytest.raises(EmptyProviderNameError):
            ProviderName("   ")

    def test_too_long_raises_error(self) -> None:
        with pytest.raises(ProviderNameTooLongError):
            ProviderName("a" * 51)


class TestProviderNameFrozen:
    """ProviderName is immutable."""

    def test_cannot_set_value(self) -> None:
        name = ProviderName("plaid")
        with pytest.raises(AttributeError):
            name.value = "other"  # type: ignore[misc]

"""Tests for ProviderCredentials value object."""

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidProviderCredentialsError,
)
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)


class TestProviderCredentialsValid:
    """Valid ProviderCredentials creation scenarios."""

    def test_valid_token(self) -> None:
        creds = ProviderCredentials("token123")
        assert creds.token == "token123"

    def test_trimming(self) -> None:
        creds = ProviderCredentials("  token  ")
        assert creds.token == "token"

    def test_long_token(self) -> None:
        long_token = "a" * 1000
        creds = ProviderCredentials(long_token)
        assert creds.token == long_token


class TestProviderCredentialsInvalid:
    """Invalid ProviderCredentials creation scenarios."""

    def test_empty_raises_error(self) -> None:
        with pytest.raises(InvalidProviderCredentialsError):
            ProviderCredentials("")

    def test_blank_raises_error(self) -> None:
        with pytest.raises(InvalidProviderCredentialsError):
            ProviderCredentials("   ")


class TestProviderCredentialsFrozen:
    """ProviderCredentials is immutable."""

    def test_cannot_set_token(self) -> None:
        creds = ProviderCredentials("token123")
        with pytest.raises(AttributeError):
            creds.token = "other"  # type: ignore[misc]

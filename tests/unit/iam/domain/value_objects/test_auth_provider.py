from datetime import UTC, datetime

import pytest

from emerald.iam.domain.models import AuthProvider, ProviderType
from emerald.shared_kernel.domain.exceptions import InvalidValueError


def _now() -> datetime:
    return datetime.now(UTC)


class TestAuthProviderConstruction:
    def test_password_provider_valid(self):
        now = _now()
        ap = AuthProvider(ProviderType.PASSWORD, None, now)
        assert ap.provider_type == ProviderType.PASSWORD
        assert ap.external_id is None

    def test_google_provider_valid(self):
        now = _now()
        ap = AuthProvider(ProviderType.GOOGLE, "google-123", now)
        assert ap.provider_type == ProviderType.GOOGLE
        assert ap.external_id == "google-123"

    def test_microsoft_provider_valid(self):
        now = _now()
        ap = AuthProvider(ProviderType.MICROSOFT, "ms-456", now)
        assert ap.provider_type == ProviderType.MICROSOFT
        assert ap.external_id == "ms-456"

    def test_password_with_external_id_raises(self):
        with pytest.raises(InvalidValueError):
            AuthProvider(ProviderType.PASSWORD, "some-id", _now())

    def test_google_without_external_id_raises(self):
        with pytest.raises(InvalidValueError):
            AuthProvider(ProviderType.GOOGLE, None, _now())

    def test_google_with_empty_external_id_raises(self):
        with pytest.raises(InvalidValueError):
            AuthProvider(ProviderType.GOOGLE, "  ", _now())

    def test_microsoft_without_external_id_raises(self):
        with pytest.raises(InvalidValueError):
            AuthProvider(ProviderType.MICROSOFT, None, _now())

    def test_naive_datetime_raises(self):
        with pytest.raises(InvalidValueError):
            AuthProvider(ProviderType.PASSWORD, None, datetime(2026, 1, 1))


class TestAuthProviderEquality:
    def test_same_provider_type_equal(self):
        now = _now()
        ap1 = AuthProvider(ProviderType.GOOGLE, "id-1", now)
        ap2 = AuthProvider(ProviderType.GOOGLE, "id-2", now)
        assert ap1 == ap2

    def test_different_provider_type_not_equal(self):
        now = _now()
        ap1 = AuthProvider(ProviderType.PASSWORD, None, now)
        ap2 = AuthProvider(ProviderType.GOOGLE, "id-1", now)
        assert ap1 != ap2

    def test_same_hash_for_same_type(self):
        now = _now()
        ap1 = AuthProvider(ProviderType.GOOGLE, "id-1", now)
        ap2 = AuthProvider(ProviderType.GOOGLE, "id-2", now)
        assert hash(ap1) == hash(ap2)

    def test_usable_in_set(self):
        now = _now()
        providers = {
            AuthProvider(ProviderType.PASSWORD, None, now),
            AuthProvider(ProviderType.GOOGLE, "g-1", now),
            AuthProvider(ProviderType.GOOGLE, "g-2", now),
        }
        assert len(providers) == 2


class TestAuthProviderImmutability:
    def test_frozen(self):
        ap = AuthProvider(ProviderType.PASSWORD, None, _now())
        with pytest.raises(AttributeError):
            ap.provider_type = ProviderType.GOOGLE  # type: ignore[misc]

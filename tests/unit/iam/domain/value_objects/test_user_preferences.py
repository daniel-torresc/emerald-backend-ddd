import pytest

from emerald.iam.domain.models import UserPreferences
from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models import Currency


class TestUserPreferencesDefaults:
    def test_default_values(self):
        prefs = UserPreferences()
        assert prefs.timezone == "UTC"
        assert prefs.locale == "en-US"
        assert prefs.display_currency == Currency.USD


class TestUserPreferencesValidation:
    def test_empty_timezone_raises(self):
        with pytest.raises(InvalidValueError):
            UserPreferences(timezone="")

    def test_whitespace_timezone_raises(self):
        with pytest.raises(InvalidValueError):
            UserPreferences(timezone="   ")

    def test_empty_locale_raises(self):
        with pytest.raises(InvalidValueError):
            UserPreferences(locale="")

    def test_whitespace_locale_raises(self):
        with pytest.raises(InvalidValueError):
            UserPreferences(locale="   ")

    def test_custom_values(self):
        prefs = UserPreferences(
            timezone="America/New_York",
            locale="es-MX",
            display_currency=Currency.EUR,
        )
        assert prefs.timezone == "America/New_York"
        assert prefs.locale == "es-MX"
        assert prefs.display_currency == Currency.EUR


class TestUserPreferencesEquality:
    def test_equal_by_all_fields(self):
        p1 = UserPreferences()
        p2 = UserPreferences()
        assert p1 == p2

    def test_not_equal_different_timezone(self):
        p1 = UserPreferences(timezone="UTC")
        p2 = UserPreferences(timezone="US/Eastern")
        assert p1 != p2


class TestUserPreferencesImmutability:
    def test_frozen(self):
        prefs = UserPreferences()
        with pytest.raises(AttributeError):
            prefs.timezone = "other"  # type: ignore[misc]

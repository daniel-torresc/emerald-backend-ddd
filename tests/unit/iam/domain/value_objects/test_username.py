import pytest

from emerald.iam.domain.exceptions import InvalidUsernameError
from emerald.iam.domain.models import Username


class TestUsernameConstruction:
    def test_valid_username(self):
        u = Username("johndoe")
        assert u.value == "johndoe"

    def test_normalizes_to_lowercase(self):
        u = Username("JohnDoe")
        assert u.value == "johndoe"

    def test_too_short_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("ab")

    def test_too_long_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("a" * 31)

    def test_starts_with_underscore_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("_john")

    def test_ends_with_hyphen_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("john-")

    def test_starts_with_hyphen_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("-john")

    def test_ends_with_underscore_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("john_")

    def test_space_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("john doe")

    def test_special_char_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("john@doe")

    def test_valid_with_underscore_and_hyphen(self):
        u = Username("john_doe-123")
        assert u.value == "john_doe-123"

    def test_consecutive_special_chars_allowed(self):
        u = Username("a--b")
        assert u.value == "a--b"

    def test_exactly_3_chars(self):
        u = Username("abc")
        assert u.value == "abc"

    def test_exactly_30_chars(self):
        u = Username("a" * 30)
        assert u.value == "a" * 30

    def test_empty_raises(self):
        with pytest.raises(InvalidUsernameError):
            Username("")


class TestUsernameEquality:
    def test_equal_case_insensitive(self):
        assert Username("john") == Username("JOHN")

    def test_not_equal_different(self):
        assert Username("john") != Username("jane")

    def test_same_hash(self):
        assert hash(Username("john")) == hash(Username("JOHN"))


class TestUsernameStr:
    def test_str_returns_normalized(self):
        assert str(Username("JohnDoe")) == "johndoe"


class TestUsernameImmutability:
    def test_frozen(self):
        u = Username("johndoe")
        with pytest.raises(AttributeError):
            u.value = "other"  # type: ignore[misc]

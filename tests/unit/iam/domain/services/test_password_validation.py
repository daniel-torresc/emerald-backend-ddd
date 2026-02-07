import pytest

from emerald.iam.domain.exceptions import PasswordReusedError, PasswordTooWeakError
from emerald.iam.domain.services import validate_not_in_history, validate_password_strength


class _FakeHasher:
    """Fake PasswordHasher that stores plaintext as 'hash' for testing."""

    def hash(self, plaintext: str) -> str:
        return f"hashed:{plaintext}"

    def verify(self, plaintext: str, hashed: str) -> bool:
        return hashed == f"hashed:{plaintext}"


class TestValidatePasswordStrength:
    def test_valid_password(self):
        validate_password_strength("ValidPass123!!")

    def test_too_short(self):
        with pytest.raises(PasswordTooWeakError, match="12 characters"):
            validate_password_strength("Short1!a")

    def test_no_uppercase(self):
        with pytest.raises(PasswordTooWeakError, match="uppercase"):
            validate_password_strength("alllowercase1!")

    def test_no_lowercase(self):
        with pytest.raises(PasswordTooWeakError, match="lowercase"):
            validate_password_strength("ALLUPPERCASE1!")

    def test_no_digit(self):
        with pytest.raises(PasswordTooWeakError, match="digit"):
            validate_password_strength("NoDigitsHere!!")

    def test_no_special_char(self):
        with pytest.raises(PasswordTooWeakError, match="special"):
            validate_password_strength("NoSpecialChar1a")

    def test_multiple_failures_reported(self):
        with pytest.raises(PasswordTooWeakError) as exc_info:
            validate_password_strength("short")
        msg = str(exc_info.value)
        assert "12 characters" in msg
        assert "uppercase" in msg
        assert "digit" in msg
        assert "special" in msg

    def test_exactly_12_chars_valid(self):
        validate_password_strength("ValidPass12!")

    def test_empty_password_fails(self):
        with pytest.raises(PasswordTooWeakError):
            validate_password_strength("")


class TestValidateNotInHistory:
    def test_no_match_passes(self):
        hasher = _FakeHasher()
        validate_not_in_history("newpass", ["hashed:old1", "hashed:old2"], hasher)

    def test_match_raises(self):
        hasher = _FakeHasher()
        with pytest.raises(PasswordReusedError):
            validate_not_in_history("old1", ["hashed:old1", "hashed:old2"], hasher)

    def test_empty_history_passes(self):
        hasher = _FakeHasher()
        validate_not_in_history("anything", [], hasher)

    def test_partial_history_checked_fully(self):
        hasher = _FakeHasher()
        history = ["hashed:pw1", "hashed:pw2"]
        validate_not_in_history("newpass", history, hasher)

    def test_match_at_end_of_history(self):
        hasher = _FakeHasher()
        history = ["hashed:pw1", "hashed:pw2", "hashed:pw3"]
        with pytest.raises(PasswordReusedError):
            validate_not_in_history("pw3", history, hasher)

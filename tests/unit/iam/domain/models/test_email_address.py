import pytest

from emerald.iam.domain.exceptions import InvalidEmailError
from emerald.iam.domain.models import EmailAddress


class TestEmailAddressConstruction:
    def test_valid_email(self):
        email = EmailAddress("user@example.com")
        assert email.value == "user@example.com"

    def test_normalizes_to_lowercase(self):
        email = EmailAddress("User@Example.COM")
        assert email.value == "user@example.com"

    def test_strips_whitespace(self):
        email = EmailAddress("  user@example.com  ")
        assert email.value == "user@example.com"

    def test_empty_raises(self):
        with pytest.raises(InvalidEmailError):
            EmailAddress("")

    def test_whitespace_only_raises(self):
        with pytest.raises(InvalidEmailError):
            EmailAddress("   ")

    def test_invalid_no_at_sign(self):
        with pytest.raises(InvalidEmailError):
            EmailAddress("invalid")

    def test_invalid_no_domain(self):
        with pytest.raises(InvalidEmailError):
            EmailAddress("user@")

    def test_invalid_tld_too_short(self):
        with pytest.raises(InvalidEmailError):
            EmailAddress("a@b.c")

    def test_valid_complex_local_part(self):
        email = EmailAddress("john.doe+tag@example.co.uk")
        assert email.value == "john.doe+tag@example.co.uk"

    def test_max_length_exceeded(self):
        local = "a" * 64
        domain = "b" * 186 + ".com"
        long_email = f"{local}@{domain}"
        assert len(long_email) > 254
        with pytest.raises(InvalidEmailError):
            EmailAddress(long_email)

    def test_valid_at_max_boundary(self):
        local = "a" * 64
        domain = "b" * 183 + ".com"
        email_str = f"{local}@{domain}"
        assert len(email_str) == 252
        email = EmailAddress(email_str)
        assert email.value == email_str


class TestEmailAddressEquality:
    def test_equal_same_case(self):
        assert EmailAddress("user@example.com") == EmailAddress("user@example.com")

    def test_equal_different_case(self):
        assert EmailAddress("user@example.com") == EmailAddress("USER@EXAMPLE.COM")

    def test_not_equal_different_email(self):
        assert EmailAddress("a@example.com") != EmailAddress("b@example.com")

    def test_same_hash_for_equal(self):
        e1 = EmailAddress("user@example.com")
        e2 = EmailAddress("USER@EXAMPLE.COM")
        assert hash(e1) == hash(e2)

    def test_usable_in_set(self):
        emails = {EmailAddress("a@example.com"), EmailAddress("A@EXAMPLE.COM")}
        assert len(emails) == 1


class TestEmailAddressStr:
    def test_str_returns_normalized(self):
        email = EmailAddress("User@Example.COM")
        assert str(email) == "user@example.com"


class TestEmailAddressImmutability:
    def test_frozen(self):
        email = EmailAddress("user@example.com")
        with pytest.raises(AttributeError):
            email.value = "other@example.com"  # type: ignore[misc]

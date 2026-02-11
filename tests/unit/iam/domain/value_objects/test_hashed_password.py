import pytest

from emerald.iam.domain.models import HashedPassword
from emerald.shared_kernel.domain.exceptions import InvalidValueError


class TestHashedPasswordConstruction:
    def test_valid_hash(self):
        hp = HashedPassword("$argon2id$v=19$hash")
        assert hp.hashed_value == "$argon2id$v=19$hash"

    def test_empty_raises(self):
        with pytest.raises(InvalidValueError):
            HashedPassword("")


class TestHashedPasswordEquality:
    def test_equal_same_hash(self):
        assert HashedPassword("abc") == HashedPassword("abc")

    def test_not_equal_different_hash(self):
        assert HashedPassword("abc") != HashedPassword("def")

    def test_hashable(self):
        s = {HashedPassword("abc"), HashedPassword("abc")}
        assert len(s) == 1


class TestHashedPasswordImmutability:
    def test_frozen(self):
        hp = HashedPassword("abc")
        with pytest.raises(AttributeError):
            hp.hashed_value = "other"  # type: ignore[misc]

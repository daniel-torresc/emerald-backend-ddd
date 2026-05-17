import pytest

from emerald.iam.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher


@pytest.fixture
def hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


class TestArgon2PasswordHasher:
    async def test_hash_produces_argon2id_format(self, hasher: Argon2PasswordHasher) -> None:
        hashed = await hasher.hash("my-password")
        assert hashed.startswith("$argon2id$")

    async def test_verify_correct_password(self, hasher: Argon2PasswordHasher) -> None:
        hashed = await hasher.hash("my-password")
        assert await hasher.verify("my-password", hashed) is True

    async def test_verify_wrong_password(self, hasher: Argon2PasswordHasher) -> None:
        hashed = await hasher.hash("my-password")
        assert await hasher.verify("wrong-password", hashed) is False

    async def test_hash_produces_unique_hashes(self, hasher: Argon2PasswordHasher) -> None:
        hash1 = await hasher.hash("same-password")
        hash2 = await hasher.hash("same-password")
        assert hash1 != hash2

    async def test_verify_corrupt_hash_raises(self, hasher: Argon2PasswordHasher) -> None:
        with pytest.raises(Exception):
            await hasher.verify("password", "garbage")

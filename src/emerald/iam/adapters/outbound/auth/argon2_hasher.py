import asyncio

import argon2


class Argon2PasswordHasher:
    """Wraps argon2-cffi to implement PasswordHasherPort."""

    def __init__(self) -> None:
        self._hasher = argon2.PasswordHasher()

    async def hash(self, plaintext: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, plaintext)

    async def verify(self, plaintext: str, hashed: str) -> bool:
        try:
            return await asyncio.to_thread(self._hasher.verify, hashed, plaintext)
        except argon2.exceptions.VerifyMismatchError:
            return False

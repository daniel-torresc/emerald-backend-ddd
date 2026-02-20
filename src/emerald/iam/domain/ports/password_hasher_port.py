from typing import Protocol


class PasswordHasherPort(Protocol):
    """Domain port for password hashing and verification.

    The domain defines the contract; infrastructure provides the implementation
    (e.g., Argon2id).
    """

    async def hash(self, plaintext: str) -> str:
        """Hash a plaintext password, return hash string."""
        ...

    async def verify(self, plaintext: str, hashed: str) -> bool:
        """Verify plaintext against a stored hash."""
        ...

from typing import Protocol


class PasswordHasher(Protocol):
    """Domain port for password hashing and verification.

    The domain defines the contract; infrastructure provides the implementation
    (e.g., Argon2id).
    """

    def hash(self, plaintext: str) -> str:
        """Hash a plaintext password, return hash string."""
        ...

    def verify(self, plaintext: str, hashed: str) -> bool:
        """Verify plaintext against a stored hash."""
        ...

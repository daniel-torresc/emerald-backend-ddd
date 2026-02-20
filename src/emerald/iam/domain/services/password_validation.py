from __future__ import annotations

from typing import TYPE_CHECKING

from emerald.iam.domain.constants import PASSWORD_MIN_LENGTH
from emerald.iam.domain.exceptions import PasswordReusedError, PasswordTooWeakError

if TYPE_CHECKING:
    from emerald.iam.domain.ports.password_hasher_port import PasswordHasherPort


def validate_password_strength(plaintext: str) -> None:
    """Validate password meets all strength requirements.

    Raises PasswordTooWeakError listing all failed rules.
    """
    failures: list[str] = []

    if len(plaintext) < PASSWORD_MIN_LENGTH:
        failures.append(f"at least {PASSWORD_MIN_LENGTH} characters")
    if not any(c.isupper() for c in plaintext):
        failures.append("at least 1 uppercase letter")
    if not any(c.islower() for c in plaintext):
        failures.append("at least 1 lowercase letter")
    if not any(c.isdigit() for c in plaintext):
        failures.append("at least 1 digit")
    if not any(not c.isalnum() for c in plaintext):
        failures.append("at least 1 special character")

    if failures:
        rules = ", ".join(failures)
        raise PasswordTooWeakError(f"Password must contain: {rules}")


async def validate_not_in_history(
    plaintext: str, history: list[str], hasher: PasswordHasherPort
) -> None:
    """Check password is not in recent history.

    Raises PasswordReusedError if plaintext matches any stored hash.
    """
    for hashed in history:
        if await hasher.verify(plaintext, hashed):
            raise PasswordReusedError("Password matches a recently used password")

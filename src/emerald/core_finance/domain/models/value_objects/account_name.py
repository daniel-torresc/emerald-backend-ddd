from dataclasses import dataclass

from emerald.core_finance.domain.exceptions import InvalidAccountNameError

_MAX_ACCOUNT_NAME_LENGTH = 100


@dataclass(frozen=True, eq=False)
class AccountName:
    """User-defined account name with case-insensitive equality.

    Stores the trimmed, original-case value.
    Equality and hashing are case-insensitive via normalized().
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidAccountNameError("Account name must not be empty")
        if len(trimmed) > _MAX_ACCOUNT_NAME_LENGTH:
            raise InvalidAccountNameError(
                f"Account name must not exceed {_MAX_ACCOUNT_NAME_LENGTH} characters"
            )
        object.__setattr__(self, "value", trimmed)

    def normalized(self) -> str:
        """Lowercase, trimmed version for uniqueness checks."""
        return self.value.lower()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AccountName):
            return NotImplemented
        return self.normalized() == other.normalized()

    def __hash__(self) -> int:
        return hash(self.normalized())

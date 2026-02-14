from dataclasses import dataclass

from emerald.classification.domain.constants import MAX_TERM_NAME_LENGTH
from emerald.classification.domain.exceptions import InvalidTermNameError


@dataclass(frozen=True, eq=False)
class TermName:
    """Term display name with case-insensitive equality."""

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidTermNameError("Term name must not be empty")
        if len(trimmed) > MAX_TERM_NAME_LENGTH:
            raise InvalidTermNameError(
                f"Term name must not exceed {MAX_TERM_NAME_LENGTH} characters"
            )
        object.__setattr__(self, "value", trimmed)

    def normalized(self) -> str:
        """Lowercase, trimmed version for uniqueness checks."""
        return self.value.lower()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TermName):
            return NotImplemented
        return self.normalized() == other.normalized()

    def __hash__(self) -> int:
        return hash(self.normalized())

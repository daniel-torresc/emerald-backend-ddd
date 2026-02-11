import re
from dataclasses import dataclass

from emerald.iam.domain.exceptions import InvalidUsernameError

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]*[a-zA-Z0-9]$")
_MIN_LENGTH = 3
_MAX_LENGTH = 30


@dataclass(frozen=True)
class Username:
    """Validated, normalized username."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidUsernameError("Username cannot be empty")
        normalized = self.value.strip().lower()
        if len(normalized) < _MIN_LENGTH:
            raise InvalidUsernameError(
                f"Username must be at least {_MIN_LENGTH} characters, got {len(normalized)}"
            )
        if len(normalized) > _MAX_LENGTH:
            raise InvalidUsernameError(
                f"Username must be at most {_MAX_LENGTH} characters, got {len(normalized)}"
            )
        if not _USERNAME_PATTERN.match(normalized):
            raise InvalidUsernameError(
                f"Username contains invalid characters or starts/ends with _ or -: {self.value}"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

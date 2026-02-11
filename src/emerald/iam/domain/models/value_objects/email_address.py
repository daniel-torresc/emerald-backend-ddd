import re
from dataclasses import dataclass

from emerald.iam.domain.exceptions import InvalidEmailError

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_MAX_EMAIL_LENGTH = 254


@dataclass(frozen=True)
class EmailAddress:
    """Validated, normalized email address."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise InvalidEmailError("Email address cannot be empty")
        normalized = self.value.strip().lower()
        if len(normalized) > _MAX_EMAIL_LENGTH:
            raise InvalidEmailError(
                f"Email address exceeds maximum length of {_MAX_EMAIL_LENGTH} characters"
            )
        if not _EMAIL_PATTERN.match(normalized):
            raise InvalidEmailError(f"Invalid email format: {self.value}")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

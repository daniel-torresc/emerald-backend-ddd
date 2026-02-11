from dataclasses import dataclass

from emerald.shared_kernel.domain.exceptions import InvalidValueError


@dataclass(frozen=True)
class HashedPassword:
    """Holds a pre-hashed password string. Never contains plaintext."""

    hashed_value: str

    def __post_init__(self) -> None:
        if not self.hashed_value:
            raise InvalidValueError("Hashed password cannot be empty")

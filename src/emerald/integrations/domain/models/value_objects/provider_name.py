from dataclasses import dataclass

from emerald.integrations.domain.constants import MAX_PROVIDER_NAME_LENGTH
from emerald.integrations.domain.exceptions.connection_exceptions import (
    EmptyProviderNameError,
    ProviderNameTooLongError,
)


@dataclass(frozen=True)
class ProviderName:
    """Validated provider identifier, lowercase normalized."""

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise EmptyProviderNameError()
        normalized = stripped.lower()
        if len(normalized) > MAX_PROVIDER_NAME_LENGTH:
            raise ProviderNameTooLongError(
                f"Provider name must not exceed {MAX_PROVIDER_NAME_LENGTH} characters"
            )
        object.__setattr__(self, "value", normalized)

from dataclasses import dataclass

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidProviderCredentialsError,
)


@dataclass(frozen=True)
class ProviderCredentials:
    """Opaque credential token for a bank provider."""

    token: str

    def __post_init__(self) -> None:
        stripped = self.token.strip()
        if not stripped:
            raise InvalidProviderCredentialsError()
        object.__setattr__(self, "token", stripped)

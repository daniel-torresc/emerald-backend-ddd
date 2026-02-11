from dataclasses import dataclass

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models import Currency


@dataclass(frozen=True)
class UserPreferences:
    """User display and localization settings."""

    timezone: str = "UTC"
    locale: str = "en-US"
    display_currency: Currency = Currency.USD

    def __post_init__(self) -> None:
        if not self.timezone or not self.timezone.strip():
            raise InvalidValueError("Timezone cannot be empty")
        if not self.locale or not self.locale.strip():
            raise InvalidValueError("Locale cannot be empty")

from datetime import datetime
from typing import Any, Protocol

from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)


class BankProviderAdapter(Protocol):
    """Outbound port for communicating with external bank aggregation services."""

    def fetch_transactions(
        self,
        credentials: ProviderCredentials,
        external_account_id: str,
        since: datetime | None = None,
    ) -> list[str]: ...

    def verify_credentials(self, credentials: ProviderCredentials) -> bool: ...

    def get_account_info(
        self,
        credentials: ProviderCredentials,
        external_account_id: str,
    ) -> dict[str, Any]: ...

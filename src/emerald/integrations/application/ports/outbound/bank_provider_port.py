from datetime import datetime
from typing import Any, Protocol

from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)


class BankProviderPort(Protocol):
    """Outbound port for communicating with external bank aggregation services."""

    async def fetch_transactions(
        self,
        credentials: ProviderCredentials,
        external_account_id: str,
        since: datetime | None = None,
    ) -> list[NormalizedTransaction]: ...

    async def verify_credentials(self, credentials: ProviderCredentials) -> bool: ...

    async def get_account_info(
        self,
        credentials: ProviderCredentials,
        external_account_id: str,
    ) -> dict[str, Any]: ...

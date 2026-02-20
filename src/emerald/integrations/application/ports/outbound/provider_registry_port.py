from typing import Protocol

from emerald.integrations.application.ports.outbound.bank_provider_port import (
    BankProviderPort,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName


class BankProviderRegistryPort(Protocol):
    """Resolves the correct provider adapter by provider name."""

    async def get_adapter(self, provider_name: ProviderName) -> BankProviderPort: ...

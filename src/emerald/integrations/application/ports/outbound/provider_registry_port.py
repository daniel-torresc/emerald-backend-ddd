from typing import Protocol

from emerald.integrations.application.ports.outbound.bank_provider_port import (
    BankProviderPort,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.integrations.domain.ports.transaction_normalizer_port import TransactionNormalizerPort


class BankProviderRegistryPort(Protocol):
    """Resolves the correct provider adapter and normalizer by provider name."""

    async def get_adapter(self, provider_name: ProviderName) -> BankProviderPort: ...

    async def get_normalizer(self, provider_name: ProviderName) -> TransactionNormalizerPort: ...

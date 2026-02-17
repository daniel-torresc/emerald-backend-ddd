from typing import Protocol

from emerald.integrations.application.ports.outbound.bank_provider_adapter import (
    BankProviderAdapter,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.integrations.domain.ports.transaction_normalizer import TransactionNormalizer


class BankProviderAdapterRegistry(Protocol):
    """Resolves the correct provider adapter and normalizer by provider name."""

    def get_adapter(self, provider_name: ProviderName) -> BankProviderAdapter: ...

    def get_normalizer(self, provider_name: ProviderName) -> TransactionNormalizer: ...

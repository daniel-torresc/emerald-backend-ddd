import uuid
from datetime import datetime
from typing import Protocol

from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName


class BankConnectionRepository(Protocol):
    """Port for bank connection persistence."""

    def save(self, connection: BankConnection) -> None: ...

    def find_by_id(
        self, connection_id: uuid.UUID, include_deleted: bool = False
    ) -> BankConnection | None: ...

    def find_by_user(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> list[BankConnection]: ...

    def find_by_account(self, account_id: uuid.UUID) -> list[BankConnection]: ...

    def find_by_account_and_provider(
        self, account_id: uuid.UUID, provider_name: ProviderName
    ) -> BankConnection | None: ...

    def find_due_for_sync(self, as_of: datetime) -> list[BankConnection]: ...

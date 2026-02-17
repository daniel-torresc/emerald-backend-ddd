import uuid
from datetime import date
from decimal import Decimal
from typing import Protocol

from emerald.integrations.application.dtos.transaction_match import TransactionMatch


class TransactionImportPort(Protocol):
    """ACL boundary from Integrations → Core Finance."""

    def import_transaction(
        self,
        account_id: uuid.UUID,
        transaction_date: date,
        amount: Decimal,
        currency_code: str,
        original_description: str,
        external_id: str,
        imported_by: uuid.UUID,
        value_date: date | None = None,
        merchant: str | None = None,
    ) -> uuid.UUID: ...

    def find_by_external_id(self, account_id: uuid.UUID, external_id: str) -> bool: ...

    def find_by_date_and_amount(
        self,
        account_id: uuid.UUID,
        transaction_date: date,
        amount: Decimal,
        description: str | None = None,
    ) -> list[TransactionMatch]: ...

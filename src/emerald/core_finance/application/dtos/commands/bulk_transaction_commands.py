import uuid
from dataclasses import dataclass

from emerald.core_finance.domain.models.value_objects.bulk_update_fields import BulkUpdateFields
from emerald.core_finance.domain.models.value_objects.transaction_input import TransactionInput
from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class BulkCreateTransactions(Command):
    """Command to create multiple transactions in a single request."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transactions: tuple[TransactionInput, ...] = ()
    import_source_type: str = ""
    source_id: str | None = None


@dataclass(frozen=True)
class BulkUpdateTransactions(Command):
    """Command to update multiple transactions in a single request."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_ids: tuple[uuid.UUID, ...] = ()
    updates: BulkUpdateFields | None = None


@dataclass(frozen=True)
class BulkDeleteTransactions(Command):
    """Command to soft-delete multiple transactions in a single request."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_ids: tuple[uuid.UUID, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class BulkRecoverTransactions(Command):
    """Command to recover multiple soft-deleted transactions in a single request."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_ids: tuple[uuid.UUID, ...] = ()

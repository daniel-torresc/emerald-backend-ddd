import uuid
from typing import Protocol

from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.shared_kernel.domain.models.value_objects.date_range import DateRange
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.paginated_result import PaginatedResult


class TransactionRepository(Protocol):
    """Port for transaction persistence."""

    def save(self, transaction: Transaction) -> None: ...

    def save_many(self, transactions: list[Transaction]) -> None: ...

    def find_by_id(
        self,
        transaction_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Transaction | None: ...

    def find_by_account(
        self,
        account_id: uuid.UUID,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]: ...

    def find_by_account_in_range(
        self,
        account_id: uuid.UUID,
        date_range: DateRange,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]: ...

    def find_by_external_id(
        self,
        account_id: uuid.UUID,
        external_id: str,
    ) -> Transaction | None: ...

    def count_by_account(
        self,
        account_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> int: ...

    def sum_amounts(
        self,
        account_id: uuid.UUID,
        exclude_split_parents: bool = True,
    ) -> Money: ...

    def find_children(
        self,
        parent_transaction_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> list[Transaction]: ...

    def hard_delete_children(self, parent_transaction_id: uuid.UUID) -> int: ...

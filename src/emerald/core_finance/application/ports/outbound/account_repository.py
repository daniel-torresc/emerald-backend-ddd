import uuid
from typing import Protocol

from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName


class AccountRepository(Protocol):
    """Port for account persistence."""

    def save(self, account: Account) -> None: ...

    def find_by_id(
        self, account_id: uuid.UUID, include_deleted: bool = False
    ) -> Account | None: ...

    def find_by_owner(self, user_id: uuid.UUID, include_deleted: bool = False) -> list[Account]: ...

    def exists_by_name_for_user(self, account_name: AccountName, user_id: uuid.UUID) -> bool: ...

    # TODO(spec-008): Add find_accessible_by_user(user_id, include_deleted) -> list[Account]
    #   Returns accounts where the user has any AccountShare (not just created_by).

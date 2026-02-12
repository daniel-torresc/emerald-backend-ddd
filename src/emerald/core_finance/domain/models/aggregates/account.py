from __future__ import annotations

import uuid
from typing import Any

from emerald.core_finance.domain.events.account_events import (
    AccountCreated,
    AccountRecovered,
    AccountSoftDeleted,
    AccountUpdated,
)
from emerald.core_finance.domain.exceptions import InvalidAccountNotesError
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.iban import IBAN
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.exceptions import CurrencyMismatchError
from emerald.shared_kernel.domain.models.base.aggregate_root import AggregateRoot
from emerald.shared_kernel.domain.models.base.auditable import AuditableMixin
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod

_MAX_NOTES_LENGTH = 500


class Account(SoftDeletableMixin, AuditableMixin, AggregateRoot):
    """Account aggregate root — the central consistency boundary for financial data.

    Deferred invariants:
      TODO(spec-008): Exactly ONE owner share per account
      TODO(spec-008): One active share per user max
      TODO(spec-009): All transactions must match account currency
    """

    def __init__(
        self,
        *,
        account_name: AccountName,
        account_type_id: uuid.UUID,
        financial_institution_id: uuid.UUID,
        currency: Currency,
        opening_balance: Money,
        iban: IBAN | None = None,
        notes: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.account_name = account_name
        self.account_type_id = account_type_id
        self.financial_institution_id = financial_institution_id
        self._currency = currency
        self._opening_balance = opening_balance
        self._iban = iban
        self.notes = notes

    # -- Immutable properties --------------------------------------------------

    @property
    def currency(self) -> Currency:
        return self._currency

    @property
    def opening_balance(self) -> Money:
        return self._opening_balance

    @property
    def iban(self) -> IBAN | None:
        return self._iban

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def create(
        cls,
        owner: UserReference,
        account_name: AccountName,
        currency: Currency,
        opening_balance: Money,
        account_type_id: uuid.UUID,
        financial_institution_id: uuid.UUID,
        iban: IBAN | None = None,
        notes: str | None = None,
    ) -> Account:
        """Create a new Account with all invariants validated."""
        if opening_balance.currency != currency:
            raise CurrencyMismatchError(
                f"Opening balance currency {opening_balance.currency.code} "
                f"does not match account currency {currency.code}"
            )
        if notes is not None and len(notes) > _MAX_NOTES_LENGTH:
            raise InvalidAccountNotesError(
                f"Account notes must not exceed {_MAX_NOTES_LENGTH} characters"
            )

        account_id = uuid.uuid4()
        account = cls(
            account_name=account_name,
            account_type_id=account_type_id,
            financial_institution_id=financial_institution_id,
            currency=currency,
            opening_balance=opening_balance,
            iban=iban,
            notes=notes,
            id=account_id,
            created_by=owner.user_id,
            version=1,
        )
        # TODO(spec-008): Create an OWNER AccountShare for the creator.
        #   Until then, account.created_by identifies the owner.
        account._register_event(
            AccountCreated(
                aggregate_id=account.id,
                owner_user_id=owner.user_id,
                currency_code=currency.code,
                account_name=account_name.value,
                opening_balance=opening_balance.amount,
            )
        )
        return account

    # -- Update methods --------------------------------------------------------

    def update_name(self, new_name: AccountName, updated_by: uuid.UUID) -> None:
        """Update account name."""
        self.account_name = new_name
        self._touch()
        self._set_updated_by(updated_by)
        self._register_event(
            AccountUpdated(
                aggregate_id=self.id,
                updated_by=updated_by,
                changed_fields=frozenset({"account_name"}),
            )
        )

    def update_account_type(self, account_type_id: uuid.UUID, updated_by: uuid.UUID) -> None:
        """Update account type reference."""
        self.account_type_id = account_type_id
        self._touch()
        self._set_updated_by(updated_by)
        self._register_event(
            AccountUpdated(
                aggregate_id=self.id,
                updated_by=updated_by,
                changed_fields=frozenset({"account_type_id"}),
            )
        )

    def update_financial_institution(
        self, institution_id: uuid.UUID, updated_by: uuid.UUID
    ) -> None:
        """Update financial institution reference."""
        self.financial_institution_id = institution_id
        self._touch()
        self._set_updated_by(updated_by)
        self._register_event(
            AccountUpdated(
                aggregate_id=self.id,
                updated_by=updated_by,
                changed_fields=frozenset({"financial_institution_id"}),
            )
        )

    def update_notes(self, notes: str | None, updated_by: uuid.UUID) -> None:
        """Update account notes."""
        if notes is not None and len(notes) > _MAX_NOTES_LENGTH:
            raise InvalidAccountNotesError(
                f"Account notes must not exceed {_MAX_NOTES_LENGTH} characters"
            )
        self.notes = notes
        self._touch()
        self._set_updated_by(updated_by)
        self._register_event(
            AccountUpdated(
                aggregate_id=self.id,
                updated_by=updated_by,
                changed_fields=frozenset({"notes"}),
            )
        )

    # -- Balance calculation (stub) --------------------------------------------

    def calculate_balance(self) -> Money:
        """Return the current balance. Stub: returns opening_balance until Spec 009."""
        # TODO(spec-009): Return opening_balance + sum(t.amount for t in transactions
        #   where t.deleted_at IS NULL and t.parent_transaction_id IS NULL)
        return self._opening_balance

    @property
    def transaction_count(self) -> int:
        """Return the number of transactions. Stub: returns 0 until Spec 009."""
        # TODO(spec-009): Return count of non-deleted transactions belonging to this account
        return 0

    # -- Lifecycle methods -----------------------------------------------------

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """Soft-delete the account."""
        # TODO(spec-008): Cascade soft-delete to AccountShares
        # TODO(spec-009): Cascade soft-delete to Transactions
        # TODO(spec-011): Cascade soft-delete to Cards
        super().soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
        self._touch()
        self._register_event(
            AccountSoftDeleted(
                aggregate_id=self.id,
                deleted_by=deleted_by,
                reason=reason,
            )
        )

    def recover(self) -> None:
        """Recover a soft-deleted account."""
        # TODO(spec-008/009/011): Children (shares, transactions, cards) remain in trash
        #   and must be recovered individually per Spec 006 patterns.
        # Capture deleted_by before recovery clears it, to use as recovered_by
        recovered_by = self.deleted_by
        super().recover()
        self._touch()
        self._register_event(
            AccountRecovered(
                aggregate_id=self.id,
                recovered_by=recovered_by if recovered_by is not None else uuid.UUID(int=0),
            )
        )

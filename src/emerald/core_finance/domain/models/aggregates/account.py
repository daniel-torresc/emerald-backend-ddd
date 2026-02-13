from __future__ import annotations

import uuid
from typing import Any

from emerald.core_finance.domain.constants import MAX_CARDS_PER_ACCOUNT, MAX_SHARES_PER_ACCOUNT
from emerald.core_finance.domain.events.account_events import (
    AccountCreated,
    AccountRecovered,
    AccountSoftDeleted,
    AccountUpdated,
)
from emerald.core_finance.domain.events.card_events import (
    CardCreated,
    CardRecovered,
    CardSoftDeleted,
    CardUpdated,
)
from emerald.core_finance.domain.events.sharing_events import (
    AccountOwnershipTransferred,
    AccountShared,
    AccountShareLeft,
    AccountShareRevoked,
    AccountShareUpdated,
)
from emerald.core_finance.domain.exceptions import InvalidAccountNotesError
from emerald.core_finance.domain.exceptions.card_exceptions import (
    CardNotFoundError,
    MaxCardsReachedError,
)
from emerald.core_finance.domain.exceptions.card_exceptions import (
    CurrencyMismatchError as CardCurrencyMismatchError,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    AlreadyOwnerError,
    AlreadySharedError,
    CannotGrantOwnerError,
    CannotLeaveAsOwnerError,
    CannotModifyOwnerShareError,
    CannotRevokeOwnerError,
    CannotShareWithSelfError,
    InsufficientPermissionError,
    MaxSharesReachedError,
    ShareNotFoundError,
)
from emerald.core_finance.domain.models.entities.account_share import AccountShare
from emerald.core_finance.domain.models.entities.card import Card
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.card_network import CardNetwork
from emerald.core_finance.domain.models.value_objects.iban import IBAN
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
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
    """Account aggregate root — the central consistency boundary for financial data."""

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
        shares: list[AccountShare] | None = None,
        cards: list[Card] | None = None,
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
        self._shares: list[AccountShare] = shares if shares is not None else []
        self._cards: list[Card] = cards if cards is not None else []

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
        # Create initial OWNER share for the creator
        owner_share = AccountShare(
            account_id=account.id,
            user_id=owner.user_id,
            permission_level=PermissionLevel.OWNER,
            granted_by=owner.user_id,
        )
        account._shares.append(owner_share)
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

    # -- Share management methods ----------------------------------------------

    def share_with(
        self,
        user_id: uuid.UUID,
        permission: PermissionLevel,
        granted_by: uuid.UUID,
    ) -> AccountShare:
        """Grant access to a user at the specified permission level."""
        if self.is_deleted():
            raise AccountNotActiveError()
        if not self.is_owner(granted_by):
            raise InsufficientPermissionError(
                f"User {granted_by} does not have OWNER permission on account {self.id}"
            )
        if permission == PermissionLevel.OWNER:
            raise CannotGrantOwnerError()
        if user_id == granted_by:
            raise CannotShareWithSelfError()
        if self._find_active_share(user_id) is not None:
            raise AlreadySharedError()
        if self.active_share_count >= MAX_SHARES_PER_ACCOUNT:
            raise MaxSharesReachedError()

        share = AccountShare(
            account_id=self.id,
            user_id=user_id,
            permission_level=permission,
            granted_by=granted_by,
        )
        self._shares.append(share)
        self._register_event(
            AccountShared(
                aggregate_id=self.id,
                user_id=user_id,
                permission_level=str(permission.value),
                granted_by=granted_by,
            )
        )
        self._touch()
        return share

    def update_share_permission(
        self,
        user_id: uuid.UUID,
        new_permission: PermissionLevel,
        updated_by: uuid.UUID,
    ) -> None:
        """Update a share's permission level."""
        if not self.is_owner(updated_by):
            raise InsufficientPermissionError(
                f"User {updated_by} does not have OWNER permission on account {self.id}"
            )
        share = self._find_active_share(user_id)
        if share is None:
            raise ShareNotFoundError(f"No active share for user {user_id} on account {self.id}")
        if new_permission == PermissionLevel.OWNER:
            raise CannotGrantOwnerError()
        if share.permission_level == PermissionLevel.OWNER:
            raise CannotModifyOwnerShareError()

        old_permission = share.permission_level
        share.update_permission(new_permission)
        self._register_event(
            AccountShareUpdated(
                aggregate_id=self.id,
                user_id=user_id,
                old_permission=str(old_permission.value),
                new_permission=str(new_permission.value),
                updated_by=updated_by,
            )
        )
        self._touch()

    def revoke_share(self, user_id: uuid.UUID, revoked_by: uuid.UUID) -> None:
        """Revoke a user's share (owner-initiated)."""
        if not self.is_owner(revoked_by):
            raise InsufficientPermissionError(
                f"User {revoked_by} does not have OWNER permission on account {self.id}"
            )
        share = self._find_active_share(user_id)
        if share is None:
            raise ShareNotFoundError(f"No active share for user {user_id} on account {self.id}")
        if share.permission_level == PermissionLevel.OWNER:
            raise CannotRevokeOwnerError()

        share.revoke(revoked_by)
        self._register_event(
            AccountShareRevoked(
                aggregate_id=self.id,
                user_id=user_id,
                revoked_by=revoked_by,
            )
        )
        self._touch()

    def leave_share(self, user_id: uuid.UUID) -> None:
        """Non-owner voluntarily removes their own share."""
        share = self._find_active_share(user_id)
        if share is None:
            raise ShareNotFoundError(f"No active share for user {user_id} on account {self.id}")
        if share.permission_level == PermissionLevel.OWNER:
            raise CannotLeaveAsOwnerError()

        share.revoke(user_id)
        self._register_event(
            AccountShareLeft(
                aggregate_id=self.id,
                user_id=user_id,
            )
        )
        self._touch()

    def transfer_ownership(self, new_owner_id: uuid.UUID, current_owner_id: uuid.UUID) -> None:
        """Transfer ownership to another shared user."""
        if not self.is_owner(current_owner_id):
            raise InsufficientPermissionError(
                f"User {current_owner_id} does not have OWNER permission on account {self.id}"
            )
        if new_owner_id == current_owner_id:
            raise AlreadyOwnerError()
        new_owner_share = self._find_active_share(new_owner_id)
        if new_owner_share is None:
            raise ShareNotFoundError(
                f"No active share for user {new_owner_id} on account {self.id}"
            )

        current_owner_share = self._get_owner_share()
        current_owner_share.update_permission(PermissionLevel.EDITOR)
        new_owner_share.update_permission(PermissionLevel.OWNER)
        self._register_event(
            AccountOwnershipTransferred(
                aggregate_id=self.id,
                old_owner_id=current_owner_id,
                new_owner_id=new_owner_id,
            )
        )
        self._touch()

    # -- Authorization check methods -------------------------------------------

    def get_share_for_user(self, user_id: uuid.UUID) -> AccountShare | None:
        """Return the active share for a user, or None."""
        return self._find_active_share(user_id)

    def get_permission_level(self, user_id: uuid.UUID) -> PermissionLevel | None:
        """Return the permission level for a user, or None."""
        share = self._find_active_share(user_id)
        return share.permission_level if share is not None else None

    def has_permission(self, user_id: uuid.UUID, required: PermissionLevel) -> bool:
        """Check if user has at least the required permission level."""
        share = self._find_active_share(user_id)
        return share is not None and share.permission_level.has_at_least(required)

    def is_owner(self, user_id: uuid.UUID) -> bool:
        """Check if user is the account owner."""
        return self.has_permission(user_id, PermissionLevel.OWNER)

    def can_edit(self, user_id: uuid.UUID) -> bool:
        """Check if user has at least EDITOR permission."""
        return self.has_permission(user_id, PermissionLevel.EDITOR)

    def can_view(self, user_id: uuid.UUID) -> bool:
        """Check if user has at least VIEWER permission."""
        return self.has_permission(user_id, PermissionLevel.VIEWER)

    def get_active_shares(self) -> list[AccountShare]:
        """Return all non-revoked shares."""
        return [s for s in self._shares if s.is_active()]

    def get_owner(self) -> AccountShare:
        """Return the OWNER share (always exactly one active)."""
        return self._get_owner_share()

    @property
    def active_share_count(self) -> int:
        """Return the count of active (non-revoked) shares."""
        return sum(1 for s in self._shares if s.is_active())

    # -- Lifecycle methods -----------------------------------------------------

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """Soft-delete the account, cascading to cards and shares."""
        # 1. Cascade soft-delete active cards (no individual CardSoftDeleted events)
        for card in self._cards:
            if not card.is_deleted():
                card.soft_delete(deleted_by=deleted_by, retention=retention)
        # 2. Cascade: revoke all non-owner active shares
        for share in self._shares:
            if share.is_active() and share.permission_level != PermissionLevel.OWNER:
                share.revoke(deleted_by)
        # TODO(spec-009): Cascade soft-delete to Transactions
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
        """Recover a soft-deleted account. Shares remain revoked, cards remain deleted."""
        recovered_by = self.deleted_by
        super().recover()
        self._touch()
        self._register_event(
            AccountRecovered(
                aggregate_id=self.id,
                recovered_by=recovered_by if recovered_by is not None else uuid.UUID(int=0),
            )
        )

    # -- Card lifecycle methods ------------------------------------------------

    def add_card(self, card: Card) -> None:
        """Add a card to this account."""
        if self.is_deleted():
            raise AccountNotActiveError()
        if card.account_id != self.id:
            from emerald.core_finance.domain.exceptions.card_exceptions import InvalidCardDataError

            raise InvalidCardDataError(
                f"Card account_id {card.account_id} does not match account {self.id}"
            )
        if self.active_card_count >= MAX_CARDS_PER_ACCOUNT:
            raise MaxCardsReachedError()
        if card.credit_limit is not None and card.credit_limit.currency != self._currency:
            raise CardCurrencyMismatchError(
                f"Credit limit currency {card.credit_limit.currency.code} "
                f"does not match account currency {self._currency.code}"
            )
        self._cards.append(card)
        self._register_event(
            CardCreated(
                aggregate_id=self.id,
                card_id=card.id,
                account_id=self.id,
                card_type=card.card_type.value,
                card_name=card.card_name,
                card_number_masked=card.card_number.masked(),
            )
        )
        self._touch()

    def remove_card(
        self,
        card_id: uuid.UUID,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """Soft-delete a card."""
        card = self._find_card(card_id, include_deleted=True)
        if card is None:
            raise CardNotFoundError(f"Card {card_id} not found in account {self.id}")
        card.soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
        self._register_event(
            CardSoftDeleted(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                deleted_by=deleted_by,
            )
        )
        self._touch()

    def recover_card(self, card_id: uuid.UUID) -> None:
        """Recover a soft-deleted card."""
        if self.is_deleted():
            raise AccountNotActiveError()
        card = self._find_card(card_id, include_deleted=True)
        if card is None:
            raise CardNotFoundError(f"Card {card_id} not found in account {self.id}")
        card.recover()
        self._register_event(
            CardRecovered(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
            )
        )
        self._touch()

    # -- Card update methods ---------------------------------------------------

    def update_card_name(self, card_id: uuid.UUID, name: str) -> None:
        """Update a card's display name."""
        card = self._get_active_card(card_id)
        card.update_name(name)
        self._register_event(
            CardUpdated(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                changed_fields=["card_name"],
            )
        )
        self._touch()

    def update_card_network(self, card_id: uuid.UUID, network: CardNetwork | None) -> None:
        """Update a card's network."""
        card = self._get_active_card(card_id)
        card.update_network(network)
        self._register_event(
            CardUpdated(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                changed_fields=["card_network"],
            )
        )
        self._touch()

    def update_card_expiry(self, card_id: uuid.UUID, month: int, year: int) -> None:
        """Update a card's expiration date."""
        card = self._get_active_card(card_id)
        card.update_expiry(month, year)
        self._register_event(
            CardUpdated(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                changed_fields=["expiry_month", "expiry_year"],
            )
        )
        self._touch()

    def update_card_credit_limit(self, card_id: uuid.UUID, credit_limit: Money | None) -> None:
        """Update a card's credit limit. Validates currency match."""
        card = self._get_active_card(card_id)
        if credit_limit is not None and credit_limit.currency != self._currency:
            raise CardCurrencyMismatchError(
                f"Credit limit currency {credit_limit.currency.code} "
                f"does not match account currency {self._currency.code}"
            )
        card.update_credit_limit(credit_limit)
        self._register_event(
            CardUpdated(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                changed_fields=["credit_limit"],
            )
        )
        self._touch()

    def update_card_issuing_institution(self, card_id: uuid.UUID, institution: str | None) -> None:
        """Update a card's issuing institution."""
        card = self._get_active_card(card_id)
        card.update_issuing_institution(institution)
        self._register_event(
            CardUpdated(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                changed_fields=["issuing_institution"],
            )
        )
        self._touch()

    def update_card_notes(self, card_id: uuid.UUID, notes: str | None) -> None:
        """Update a card's notes."""
        card = self._get_active_card(card_id)
        card.update_notes(notes)
        self._register_event(
            CardUpdated(
                aggregate_id=self.id,
                card_id=card_id,
                account_id=self.id,
                changed_fields=["notes"],
            )
        )
        self._touch()

    # -- Card query methods ----------------------------------------------------

    def get_card(self, card_id: uuid.UUID, include_deleted: bool = False) -> Card | None:
        """Find a card by ID, optionally including deleted."""
        return self._find_card(card_id, include_deleted=include_deleted)

    def get_cards(self, include_deleted: bool = False) -> list[Card]:
        """Return all cards, optionally including deleted."""
        if include_deleted:
            return list(self._cards)
        return [c for c in self._cards if not c.is_deleted()]

    @property
    def active_card_count(self) -> int:
        """Return the count of non-deleted cards."""
        return sum(1 for c in self._cards if not c.is_deleted())

    # -- Private helpers -------------------------------------------------------

    def _find_card(self, card_id: uuid.UUID, include_deleted: bool = False) -> Card | None:
        """Find a card by ID."""
        for card in self._cards:
            if card.id == card_id:
                if include_deleted or not card.is_deleted():
                    return card
        return None

    def _get_active_card(self, card_id: uuid.UUID) -> Card:
        """Find an active card or raise CardNotFoundError."""
        card = self._find_card(card_id, include_deleted=False)
        if card is None:
            raise CardNotFoundError(f"Card {card_id} not found in account {self.id}")
        return card

    def _find_active_share(self, user_id: uuid.UUID) -> AccountShare | None:
        """Find an active share for a user."""
        for share in self._shares:
            if share.is_active() and share.user_id == user_id:
                return share
        return None

    def _get_owner_share(self) -> AccountShare:
        """Return the active OWNER share."""
        for share in self._shares:
            if share.is_active() and share.permission_level == PermissionLevel.OWNER:
                return share
        msg = f"Account {self.id} has no active OWNER share — invariant violated"
        raise AssertionError(msg)

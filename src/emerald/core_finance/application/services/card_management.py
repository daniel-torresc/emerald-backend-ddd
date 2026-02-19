import uuid

from emerald.core_finance.application.dtos.commands.card_commands import (
    AddCard,
    LinkTransactionToCard,
    RecoverCard,
    RemoveCard,
    UnlinkTransactionFromCard,
    UpdateCardCreditLimit,
    UpdateCardExpiry,
    UpdateCardIssuingInstitution,
    UpdateCardName,
    UpdateCardNetwork,
    UpdateCardNotes,
)
from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.exceptions import (
    AccountNotFoundError,
    CardNotFoundError,
    InsufficientPermissionError,
    TransactionNotFoundError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    TransactionDeletedError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.entities.card import Card
from emerald.core_finance.domain.models.value_objects.card_network import CardNetwork
from emerald.core_finance.domain.models.value_objects.card_number import CardNumber
from emerald.core_finance.domain.models.value_objects.card_type import CardType
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService


class CardManagementService:
    """Application service orchestrating card operations."""

    def __init__(
        self,
        uow: AbstractCoreFinanceUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention_policy_service = retention_policy_service

    # -- Card Creation ---------------------------------------------------------

    async def add_card(self, cmd: AddCard) -> Card:
        """Add a new card to an account."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)

            card_number = CardNumber(cmd.card_number)
            card_type = CardType[cmd.card_type]
            card_network = CardNetwork[cmd.card_network] if cmd.card_network is not None else None

            credit_limit: Money | None = None
            if cmd.credit_limit_amount is not None and cmd.credit_limit_currency is not None:
                currency = Currency[cmd.credit_limit_currency]
                credit_limit = Money(cmd.credit_limit_amount, currency)

            card = Card.create(
                account_id=cmd.account_id,
                card_type=card_type,
                card_name=cmd.card_name,
                card_number=card_number,
                expiry_month=cmd.expiry_month,
                expiry_year=cmd.expiry_year,
                card_network=card_network,
                credit_limit=credit_limit,
                issuing_institution=cmd.issuing_institution,
                notes=cmd.notes,
            )
            account.add_card(card)
            await self._uow.accounts.save(account)
            await self._uow.commit()
            return card

    # -- Card Updates ----------------------------------------------------------

    async def update_card_name(self, cmd: UpdateCardName) -> None:
        """Update a card's display name."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)
            account.update_card_name(cmd.card_id, cmd.card_name)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    async def update_card_network(self, cmd: UpdateCardNetwork) -> None:
        """Update a card's network."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)
            network = CardNetwork[cmd.card_network] if cmd.card_network is not None else None
            account.update_card_network(cmd.card_id, network)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    async def update_card_expiry(self, cmd: UpdateCardExpiry) -> None:
        """Update a card's expiration date."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)
            account.update_card_expiry(cmd.card_id, cmd.expiry_month, cmd.expiry_year)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    async def update_card_credit_limit(self, cmd: UpdateCardCreditLimit) -> None:
        """Update a card's credit limit."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)

            credit_limit: Money | None = None
            if cmd.credit_limit_amount is not None and cmd.credit_limit_currency is not None:
                currency = Currency[cmd.credit_limit_currency]
                credit_limit = Money(cmd.credit_limit_amount, currency)

            account.update_card_credit_limit(cmd.card_id, credit_limit)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    async def update_card_issuing_institution(self, cmd: UpdateCardIssuingInstitution) -> None:
        """Update a card's issuing institution."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)
            account.update_card_issuing_institution(cmd.card_id, cmd.issuing_institution)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    async def update_card_notes(self, cmd: UpdateCardNotes) -> None:
        """Update a card's notes."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)
            account.update_card_notes(cmd.card_id, cmd.notes)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    # -- Card Lifecycle --------------------------------------------------------

    async def remove_card(self, cmd: RemoveCard) -> None:
        """Soft-delete a card."""
        async with self._uow:
            account = await self._load_account(cmd.account_id, include_deleted=True)
            self._verify_editor(account, cmd.requesting_user_id)

            retention = await self._retention_policy_service.get_effective_retention(
                DeletableEntityType.CARD, cmd.requesting_user_id
            )
            account.remove_card(cmd.card_id, cmd.requesting_user_id, retention, cmd.reason)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    async def recover_card(self, cmd: RecoverCard) -> None:
        """Recover a soft-deleted card."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_owner(account, cmd.requesting_user_id)
            account.recover_card(cmd.card_id)
            await self._uow.accounts.save(account)
            await self._uow.commit()

    # -- Card-Transaction Linking ----------------------------------------------

    async def link_transaction_to_card(self, cmd: LinkTransactionToCard) -> None:
        """Link a transaction to a card in the same account."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)

            # Verify card exists in account (include deleted for historical linking)
            card = account.get_card(cmd.card_id, include_deleted=True)
            if card is None:
                raise CardNotFoundError(f"Card {cmd.card_id} not found in account {cmd.account_id}")

            # Load and validate transaction
            transaction = await self._uow.transactions.find_by_id(cmd.transaction_id)
            if transaction is None:
                raise TransactionNotFoundError(f"Transaction {cmd.transaction_id} not found")
            if transaction.account_id != account.id:
                raise TransactionNotFoundError(
                    f"Transaction {cmd.transaction_id} does not belong to account {account.id}"
                )
            if transaction.is_deleted():
                raise TransactionDeletedError(f"Transaction {cmd.transaction_id} is deleted")

            transaction.update_card_id(cmd.card_id)
            await self._uow.transactions.save(transaction)
            await self._uow.commit()

    async def unlink_transaction_from_card(self, cmd: UnlinkTransactionFromCard) -> None:
        """Unlink a transaction from its card."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_editor(account, cmd.requesting_user_id)

            transaction = await self._uow.transactions.find_by_id(cmd.transaction_id)
            if transaction is None:
                raise TransactionNotFoundError(f"Transaction {cmd.transaction_id} not found")
            if transaction.account_id != account.id:
                raise TransactionNotFoundError(
                    f"Transaction {cmd.transaction_id} does not belong to account {account.id}"
                )
            if transaction.is_deleted():
                raise TransactionDeletedError(f"Transaction {cmd.transaction_id} is deleted")

            transaction.update_card_id(None)
            await self._uow.transactions.save(transaction)
            await self._uow.commit()

    # -- Private helpers -------------------------------------------------------

    async def _load_account(self, account_id: uuid.UUID, include_deleted: bool = False) -> Account:
        """Load an account or raise AccountNotFoundError."""
        account = await self._uow.accounts.find_by_id(account_id, include_deleted=include_deleted)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _verify_editor(self, account: Account, requesting_user_id: uuid.UUID) -> None:
        """Verify the requesting user has at least EDITOR permission."""
        if not account.can_edit(requesting_user_id):
            raise InsufficientPermissionError(
                f"User {requesting_user_id} does not have EDITOR permission on account {account.id}"
            )

    def _verify_owner(self, account: Account, requesting_user_id: uuid.UUID) -> None:
        """Verify the requesting user is the account owner."""
        if not account.is_owner(requesting_user_id):
            raise InsufficientPermissionError(
                f"User {requesting_user_id} does not have OWNER permission on account {account.id}"
            )

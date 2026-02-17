import uuid
from datetime import UTC, datetime

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
    JoinTransactionSplits,
    RecoverTransaction,
    ReviewTransaction,
    SoftDeleteTransaction,
    SplitTransaction,
    UnreviewTransaction,
    UpdateTransactionAmount,
    UpdateTransactionComments,
    UpdateTransactionDates,
    UpdateTransactionDescription,
    UpdateTransactionMerchant,
)
from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    InsufficientPermissionError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    DuplicateExternalIdError,
    ParentAccountDeletedError,
    ParentDeletedError,
    SplitAmountMismatchError,
    TransactionDeletedError,
    TransactionNotFoundError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.import_source_type import ImportSourceType
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.shared_kernel.domain.exceptions import CurrencyMismatchError
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.date_range import DateRange
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.paginated_result import PaginatedResult
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService


class TransactionManagementService:
    """Application service orchestrating all transaction operations."""

    def __init__(
        self,
        uow: AbstractCoreFinanceUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention_policy_service = retention_policy_service

    # -- Creation --------------------------------------------------------------

    def create_transaction(self, cmd: CreateTransaction) -> Transaction:
        """Create a new transaction with all validations."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            if account.is_deleted():
                raise AccountNotActiveError()

            import_source = ImportSource(
                source_type=ImportSourceType[cmd.import_source_type],
                source_id=cmd.source_id,
                imported_at=datetime.now(UTC),
            )
            currency = Currency[cmd.currency_code]
            amount = Money(cmd.amount, currency)

            if amount.currency != account.currency:
                raise CurrencyMismatchError(
                    f"Transaction currency {amount.currency.code} "
                    f"does not match account currency {account.currency.code}"
                )

            if cmd.external_id is not None:
                existing = self._uow.transactions.find_by_external_id(
                    cmd.account_id, cmd.external_id
                )
                if existing is not None:
                    raise DuplicateExternalIdError(
                        f"External ID '{cmd.external_id}' already exists "
                        f"for account {cmd.account_id}"
                    )

            transaction = Transaction.create(
                account_id=cmd.account_id,
                transaction_date=cmd.transaction_date,
                amount=amount,
                original_description=cmd.original_description,
                created_by=cmd.requesting_user_id,
                import_source=import_source,
                value_date=cmd.value_date,
                merchant=cmd.merchant,
                comments=cmd.comments,
                external_id=cmd.external_id,
            )
            self._uow.transactions.save(transaction)
            self._uow.commit()
            return transaction

    # -- Updates ---------------------------------------------------------------

    def update_description(self, cmd: UpdateTransactionDescription) -> None:
        """Update a transaction's user description."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)
            transaction.update_description(cmd.user_description, cmd.requesting_user_id)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    def update_merchant(self, cmd: UpdateTransactionMerchant) -> None:
        """Update a transaction's merchant."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)
            transaction.update_merchant(cmd.merchant, cmd.requesting_user_id)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    def update_comments(self, cmd: UpdateTransactionComments) -> None:
        """Update a transaction's comments."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)
            transaction.update_comments(cmd.comments, cmd.requesting_user_id)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    def update_dates(self, cmd: UpdateTransactionDates) -> None:
        """Update a transaction's dates."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)
            transaction.update_dates(
                updated_by=cmd.requesting_user_id,
                transaction_date=cmd.transaction_date,
                value_date=cmd.value_date,
            )
            self._uow.transactions.save(transaction)
            self._uow.commit()

    def update_amount(self, cmd: UpdateTransactionAmount) -> None:
        """Update a transaction's amount. Auto-joins split parents; validates sum for children."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)

            currency = Currency[cmd.currency_code]
            amount = Money(cmd.amount, currency)
            if amount.currency != account.currency:
                raise CurrencyMismatchError(
                    f"Transaction currency {amount.currency.code} "
                    f"does not match account currency {account.currency.code}"
                )

            # Auto-join if updating a split parent
            if transaction.is_split_parent:
                children = self._uow.transactions.find_children(transaction.id)
                transaction.join_splits(child_count=len(children))
                self._uow.transactions.hard_delete_children(transaction.id)

            # Validate sum for split children
            if transaction.is_split_child():
                parent = self._uow.transactions.find_by_id(
                    transaction.parent_transaction_id  # type: ignore[arg-type]
                )
                if parent is not None:
                    siblings = self._uow.transactions.find_children(parent.id)
                    new_sum = Money.zero(amount.currency)
                    for sibling in siblings:
                        if sibling.id == transaction.id:
                            new_sum = new_sum + amount
                        else:
                            new_sum = new_sum + sibling.amount
                    if new_sum != parent.amount:
                        raise SplitAmountMismatchError(
                            expected=str(parent.amount),
                            actual=str(new_sum),
                        )

            transaction.update_amount(amount, cmd.requesting_user_id)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    # -- Splitting -------------------------------------------------------------

    def split_transaction(self, cmd: SplitTransaction) -> list[Transaction]:
        """Split a transaction into children."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            parent = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(parent)

            children = parent.split(list(cmd.splits), cmd.requesting_user_id)
            self._uow.transactions.save(parent)
            self._uow.transactions.save_many(children)
            self._uow.commit()
            return children

    def join_transaction_splits(self, cmd: JoinTransactionSplits) -> None:
        """Join (undo) a transaction split by hard-deleting children."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            parent = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(parent)

            children = self._uow.transactions.find_children(cmd.transaction_id)
            parent.join_splits(child_count=len(children))
            self._uow.transactions.hard_delete_children(cmd.transaction_id)
            self._uow.transactions.save(parent)
            self._uow.commit()

    # -- Review ----------------------------------------------------------------

    def review_transaction(self, cmd: ReviewTransaction) -> None:
        """Mark a transaction as reviewed."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)
            transaction.mark_as_reviewed(cmd.requesting_user_id)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    def unreview_transaction(self, cmd: UnreviewTransaction) -> None:
        """Mark a transaction as needing review."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id)
            self._verify_not_deleted(transaction)
            transaction.mark_for_review(cmd.requesting_user_id)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    # -- Lifecycle -------------------------------------------------------------

    def soft_delete_transaction(self, cmd: SoftDeleteTransaction) -> None:
        """Soft-delete a transaction. Cascades to children if split parent."""
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            transaction = self._load_transaction(cmd.transaction_id, include_deleted=True)
            retention = self._retention_policy_service.get_effective_retention(
                DeletableEntityType.TRANSACTION, cmd.requesting_user_id
            )

            # Cascade soft-delete to children if split parent
            if transaction.is_split_parent:
                children = self._uow.transactions.find_children(transaction.id)
                for child in children:
                    child.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
                    self._uow.transactions.save(child)

            transaction.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
            self._uow.transactions.save(transaction)
            self._uow.commit()

    def recover_transaction(self, cmd: RecoverTransaction) -> None:
        """Recover a soft-deleted transaction.

        Validates parent for children, cascades for parents.
        """
        with self._uow:
            account = self._load_account(cmd.account_id)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.OWNER)
            if account.is_deleted():
                raise ParentAccountDeletedError()
            transaction = self._load_transaction(cmd.transaction_id, include_deleted=True)

            # If recovering a split child, verify parent is not deleted
            if transaction.is_split_child():
                parent = self._uow.transactions.find_by_id(
                    transaction.parent_transaction_id,  # type: ignore[arg-type]
                    include_deleted=True,
                )
                if parent is not None and parent.is_deleted():
                    raise ParentDeletedError()

            # If recovering a split parent, cascade to deleted children
            if transaction.is_split_parent:
                children = self._uow.transactions.find_children(
                    transaction.id, include_deleted=True
                )
                for child in children:
                    if child.is_deleted():
                        child.recover()
                        self._uow.transactions.save(child)

            transaction.recover()
            self._uow.transactions.save(transaction)
            self._uow.commit()

    # -- Query -----------------------------------------------------------------

    def get_transaction(
        self, account_id: uuid.UUID, transaction_id: uuid.UUID, requesting_user_id: uuid.UUID
    ) -> Transaction:
        """Get a single transaction by ID."""
        with self._uow:
            account = self._load_account(account_id)
            self._verify_permission(account, requesting_user_id, PermissionLevel.VIEWER)
            transaction = self._load_transaction(transaction_id)
            return transaction

    def list_transactions(
        self,
        account_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]:
        """List transactions for an account with pagination."""
        with self._uow:
            account = self._load_account(account_id)
            self._verify_permission(account, requesting_user_id, PermissionLevel.VIEWER)
            return self._uow.transactions.find_by_account(
                account_id=account_id, page=page, page_size=page_size
            )

    def list_transactions_in_range(
        self,
        account_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        date_range: DateRange,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]:
        """List transactions for an account within a date range."""
        with self._uow:
            account = self._load_account(account_id)
            self._verify_permission(account, requesting_user_id, PermissionLevel.VIEWER)
            return self._uow.transactions.find_by_account_in_range(
                account_id=account_id, date_range=date_range, page=page, page_size=page_size
            )

    def calculate_balance(self, account_id: uuid.UUID, requesting_user_id: uuid.UUID) -> Money:
        """Calculate account balance: opening_balance + sum of transaction amounts."""
        with self._uow:
            account = self._load_account(account_id)
            self._verify_permission(account, requesting_user_id, PermissionLevel.VIEWER)
            transaction_sum = self._uow.transactions.sum_amounts(account_id)
            return account.opening_balance + transaction_sum

    def get_transaction_count(self, account_id: uuid.UUID, requesting_user_id: uuid.UUID) -> int:
        """Get the count of non-deleted transactions for an account."""
        with self._uow:
            account = self._load_account(account_id)
            self._verify_permission(account, requesting_user_id, PermissionLevel.VIEWER)
            return self._uow.transactions.count_by_account(account_id)

    # -- Private helpers -------------------------------------------------------

    def _load_account(self, account_id: uuid.UUID) -> Account:
        """Load an account or raise AccountNotFoundError."""
        account = self._uow.accounts.find_by_id(account_id, include_deleted=True)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _load_transaction(
        self, transaction_id: uuid.UUID, include_deleted: bool = False
    ) -> Transaction:
        """Load a transaction or raise TransactionNotFoundError."""
        transaction = self._uow.transactions.find_by_id(
            transaction_id, include_deleted=include_deleted
        )
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} not found")
        return transaction

    def _verify_permission(
        self, account: Account, user_id: uuid.UUID, required: PermissionLevel
    ) -> None:
        """Verify the user has at least the required permission on the account."""
        if not account.has_permission(user_id, required):
            raise InsufficientPermissionError(
                f"User {user_id} does not have {required.name} permission on account {account.id}"
            )

    def _verify_not_deleted(self, transaction: Transaction) -> None:
        """Verify the transaction is not soft-deleted."""
        if transaction.is_deleted():
            raise TransactionDeletedError()

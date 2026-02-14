import uuid
from datetime import UTC, datetime

from emerald.core_finance.application.dtos.commands.bulk_transaction_commands import (
    BulkCreateTransactions,
    BulkDeleteTransactions,
    BulkRecoverTransactions,
    BulkUpdateTransactions,
)
from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.constants import MAX_BULK_ITEMS
from emerald.core_finance.domain.events.transaction_events import (
    TransactionCreated,
    TransactionsBulkCreated,
    TransactionsBulkDeleted,
    TransactionsBulkRecovered,
    TransactionsBulkUpdated,
)
from emerald.core_finance.domain.exceptions import AccountNotFoundError
from emerald.core_finance.domain.exceptions.bulk_exceptions import (
    BulkLimitExceededError,
    EmptyBulkRequestError,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    InsufficientPermissionError,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    DuplicateExternalIdError,
    ParentDeletedError,
    TransactionDeletedError,
    TransactionNotFoundError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.bulk_result import (
    BulkFailure,
    BulkResult,
    BulkSuccess,
)
from emerald.core_finance.domain.models.value_objects.bulk_update_fields import _UnsetType
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.import_source_type import ImportSourceType
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.shared_kernel.domain.events.domain_event import DomainEvent
from emerald.shared_kernel.domain.exceptions import DomainError
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService


class BulkTransactionService:
    """Application service orchestrating bulk transaction operations."""

    def __init__(
        self,
        uow: AbstractCoreFinanceUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention_policy_service = retention_policy_service
        self._events: list[DomainEvent] = []

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear accumulated service-level events."""
        events = list(self._events)
        self._events.clear()
        return events

    # -- Bulk Create -----------------------------------------------------------

    def bulk_create_transactions(self, cmd: BulkCreateTransactions) -> BulkResult:
        """Create multiple transactions with partial-success semantics."""
        with self._uow:
            # Phase 1: Request-level validation
            account = self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            self._validate_bulk_count(len(cmd.transactions))

            # Build import source
            import_source = ImportSource(
                source_type=ImportSourceType[cmd.import_source_type],
                source_id=cmd.source_id,
                imported_at=datetime.now(UTC),
            )

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []
            seen_external_ids: set[str] = set()

            for i, txn_input in enumerate(cmd.transactions):
                try:
                    # Within-batch external_id dedup
                    if txn_input.external_id is not None:
                        if txn_input.external_id in seen_external_ids:
                            raise DuplicateExternalIdError(
                                f"Duplicate external ID '{txn_input.external_id}' within batch"
                            )
                        # Against-existing dedup
                        existing = self._uow.transactions.find_by_external_id(
                            cmd.account_id, txn_input.external_id
                        )
                        if existing is not None:
                            raise DuplicateExternalIdError(
                                f"External ID '{txn_input.external_id}' already exists "
                                f"for account {cmd.account_id}"
                            )
                        seen_external_ids.add(txn_input.external_id)

                    amount = Money(txn_input.amount, account.currency)
                    transaction = Transaction.create(
                        account_id=cmd.account_id,
                        transaction_date=txn_input.transaction_date,
                        amount=amount,
                        original_description=txn_input.original_description,
                        created_by=cmd.requesting_user_id,
                        import_source=import_source,
                        value_date=txn_input.value_date,
                        merchant=txn_input.merchant,
                        comments=txn_input.comments,
                        external_id=txn_input.external_id,
                        card_id=txn_input.card_id,
                    )
                    # Apply non-default review status
                    if txn_input.review_status != ReviewStatus.TO_REVIEW:
                        transaction.review_status = txn_input.review_status

                    self._uow.transactions.save(transaction)
                    transaction._register_event(
                        TransactionCreated(
                            aggregate_id=transaction.id,
                            account_id=cmd.account_id,
                            amount=amount.amount,
                            currency_code=amount.currency.code,
                            import_source_type=import_source.source_type.value,
                            created_by=cmd.requesting_user_id,
                        )
                    )
                    successes.append(BulkSuccess(index=i, entity_id=transaction.id))
                except DomainError as e:
                    failures.append(
                        BulkFailure(
                            index=i,
                            entity_id=None,
                            error_code=e.code,
                            error_message=str(e),
                        )
                    )

            self._uow.commit()

            result = self._build_result(successes, failures)
            self._events.append(
                TransactionsBulkCreated(
                    aggregate_id=uuid.uuid4(),
                    account_id=cmd.account_id,
                    success_count=result.success_count,
                    failure_count=result.failure_count,
                    import_source_type=cmd.import_source_type,
                    created_by=cmd.requesting_user_id,
                )
            )
            return result

    # -- Bulk Update -----------------------------------------------------------

    def bulk_update_transactions(self, cmd: BulkUpdateTransactions) -> BulkResult:
        """Update multiple transactions with partial-success semantics."""
        with self._uow:
            # Phase 1: Request-level validation
            account = self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            self._validate_bulk_count(len(cmd.transaction_ids))

            updates = cmd.updates

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []

            for i, transaction_id in enumerate(cmd.transaction_ids):
                try:
                    transaction = self._uow.transactions.find_by_id(
                        transaction_id, include_deleted=True
                    )
                    if transaction is None:
                        raise TransactionNotFoundError(f"Transaction {transaction_id} not found")
                    if transaction.is_deleted():
                        raise TransactionDeletedError()

                    # Apply non-_UNSET fields
                    if updates is not None:
                        if not isinstance(updates.review_status, _UnsetType):
                            if updates.review_status == ReviewStatus.REVIEWED:
                                transaction.mark_as_reviewed(cmd.requesting_user_id)
                            else:
                                transaction.mark_for_review(cmd.requesting_user_id)

                        if not isinstance(updates.user_description, _UnsetType):
                            transaction.update_description(
                                updates.user_description, cmd.requesting_user_id
                            )

                        if not isinstance(updates.merchant, _UnsetType):
                            transaction.update_merchant(updates.merchant, cmd.requesting_user_id)

                    self._uow.transactions.save(transaction)
                    successes.append(BulkSuccess(index=i, entity_id=transaction.id))
                except DomainError as e:
                    failures.append(
                        BulkFailure(
                            index=i,
                            entity_id=transaction_id,
                            error_code=e.code,
                            error_message=str(e),
                        )
                    )

            self._uow.commit()

            # Derive updated_fields from non-_UNSET field names
            updated_fields: set[str] = set()
            if updates is not None:
                if not isinstance(updates.review_status, _UnsetType):
                    updated_fields.add("review_status")
                if not isinstance(updates.user_description, _UnsetType):
                    updated_fields.add("user_description")
                if not isinstance(updates.merchant, _UnsetType):
                    updated_fields.add("merchant")

            result = self._build_result(successes, failures)
            self._events.append(
                TransactionsBulkUpdated(
                    aggregate_id=uuid.uuid4(),
                    account_id=cmd.account_id,
                    success_count=result.success_count,
                    failure_count=result.failure_count,
                    updated_fields=frozenset(updated_fields),
                    updated_by=cmd.requesting_user_id,
                )
            )
            return result

    # -- Bulk Delete -----------------------------------------------------------

    def bulk_delete_transactions(self, cmd: BulkDeleteTransactions) -> BulkResult:
        """Soft-delete multiple transactions with partial-success semantics."""
        with self._uow:
            # Phase 1: Request-level validation
            account = self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            self._validate_bulk_count(len(cmd.transaction_ids))

            retention = self._retention_policy_service.get_effective_retention(
                DeletableEntityType.TRANSACTION, cmd.requesting_user_id
            )

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []

            for i, transaction_id in enumerate(cmd.transaction_ids):
                try:
                    transaction = self._uow.transactions.find_by_id(
                        transaction_id, include_deleted=True
                    )
                    if transaction is None:
                        raise TransactionNotFoundError(f"Transaction {transaction_id} not found")

                    # Cascade soft-delete to children if split parent
                    if transaction.is_split_parent:
                        children = self._uow.transactions.find_children(transaction.id)
                        for child in children:
                            child.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
                            self._uow.transactions.save(child)

                    transaction.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
                    self._uow.transactions.save(transaction)
                    successes.append(BulkSuccess(index=i, entity_id=transaction.id))
                except DomainError as e:
                    failures.append(
                        BulkFailure(
                            index=i,
                            entity_id=transaction_id,
                            error_code=e.code,
                            error_message=str(e),
                        )
                    )

            self._uow.commit()

            result = self._build_result(successes, failures)
            self._events.append(
                TransactionsBulkDeleted(
                    aggregate_id=uuid.uuid4(),
                    account_id=cmd.account_id,
                    success_count=result.success_count,
                    failure_count=result.failure_count,
                    deleted_by=cmd.requesting_user_id,
                )
            )
            return result

    # -- Bulk Recover ----------------------------------------------------------

    def bulk_recover_transactions(self, cmd: BulkRecoverTransactions) -> BulkResult:
        """Recover multiple soft-deleted transactions with partial-success semantics."""
        with self._uow:
            # Phase 1: Request-level validation
            account = self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.OWNER)
            self._validate_bulk_count(len(cmd.transaction_ids))

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []

            for i, transaction_id in enumerate(cmd.transaction_ids):
                try:
                    transaction = self._uow.transactions.find_by_id(
                        transaction_id, include_deleted=True
                    )
                    if transaction is None:
                        raise TransactionNotFoundError(f"Transaction {transaction_id} not found")

                    # If recovering a split child, verify parent is not deleted
                    if transaction.is_split_child():
                        parent = self._uow.transactions.find_by_id(
                            transaction.parent_transaction_id,  # type: ignore[arg-type]
                            include_deleted=True,
                        )
                        if parent is not None and parent.is_deleted():
                            raise ParentDeletedError()

                    # Cascade recover to deleted children if split parent
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
                    successes.append(BulkSuccess(index=i, entity_id=transaction.id))
                except DomainError as e:
                    failures.append(
                        BulkFailure(
                            index=i,
                            entity_id=transaction_id,
                            error_code=e.code,
                            error_message=str(e),
                        )
                    )

            self._uow.commit()

            result = self._build_result(successes, failures)
            self._events.append(
                TransactionsBulkRecovered(
                    aggregate_id=uuid.uuid4(),
                    account_id=cmd.account_id,
                    success_count=result.success_count,
                    failure_count=result.failure_count,
                    recovered_by=cmd.requesting_user_id,
                )
            )
            return result

    # -- Private helpers -------------------------------------------------------

    def _load_account(self, account_id: uuid.UUID) -> Account:
        """Load an account or raise AccountNotFoundError."""
        account = self._uow.accounts.find_by_id(account_id, include_deleted=True)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _verify_not_deleted(self, account: Account) -> None:
        """Verify the account is not soft-deleted."""
        if account.is_deleted():
            raise AccountNotActiveError()

    def _verify_permission(
        self, account: Account, user_id: uuid.UUID, required: PermissionLevel
    ) -> None:
        """Verify the user has at least the required permission on the account."""
        if not account.has_permission(user_id, required):
            raise InsufficientPermissionError(
                f"User {user_id} does not have {required.name} permission on account {account.id}"
            )

    def _validate_bulk_count(self, count: int) -> None:
        """Validate the item count is within bounds."""
        if count == 0:
            raise EmptyBulkRequestError()
        if count > MAX_BULK_ITEMS:
            raise BulkLimitExceededError()

    @staticmethod
    def _build_result(successes: list[BulkSuccess], failures: list[BulkFailure]) -> BulkResult:
        """Construct a BulkResult from success and failure lists."""
        return BulkResult(
            success_count=len(successes),
            failure_count=len(failures),
            total_count=len(successes) + len(failures),
            successes=tuple(successes),
            failures=tuple(failures),
        )

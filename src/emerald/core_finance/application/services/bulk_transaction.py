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
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
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

    # -- Bulk Create -----------------------------------------------------------

    async def bulk_create_transactions(self, cmd: BulkCreateTransactions) -> BulkResult:
        """Create multiple transactions with partial-success semantics."""
        async with self._uow:
            # Phase 1: Request-level validation
            account = await self._load_account(cmd.account_id)
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
                        existing = await self._uow.transactions.find_by_external_id(
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

                    await self._uow.transactions.save(transaction)
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

            result = self._build_result(successes, failures)
            await self._uow.commit()
            return result

    # -- Bulk Update -----------------------------------------------------------

    async def bulk_update_transactions(self, cmd: BulkUpdateTransactions) -> BulkResult:
        """Update multiple transactions with partial-success semantics."""
        async with self._uow:
            # Phase 1: Request-level validation
            account = await self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            self._validate_bulk_count(len(cmd.transaction_ids))

            updates = cmd.updates

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []

            for i, transaction_id in enumerate(cmd.transaction_ids):
                try:
                    transaction = await self._uow.transactions.find_by_id(
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

                    await self._uow.transactions.save(transaction)
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
            await self._uow.commit()
            return result

    # -- Bulk Delete -----------------------------------------------------------

    async def bulk_delete_transactions(self, cmd: BulkDeleteTransactions) -> BulkResult:
        """Soft-delete multiple transactions with partial-success semantics."""
        async with self._uow:
            # Phase 1: Request-level validation
            account = await self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.EDITOR)
            self._validate_bulk_count(len(cmd.transaction_ids))

            retention = await self._retention_policy_service.get_effective_retention(
                DeletableEntityType.TRANSACTION, cmd.requesting_user_id
            )

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []

            for i, transaction_id in enumerate(cmd.transaction_ids):
                try:
                    transaction = await self._uow.transactions.find_by_id(
                        transaction_id, include_deleted=True
                    )
                    if transaction is None:
                        raise TransactionNotFoundError(f"Transaction {transaction_id} not found")

                    # Cascade soft-delete to children if split parent
                    if transaction.is_split_parent:
                        children = await self._uow.transactions.find_children(transaction.id)
                        for child in children:
                            child.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
                            await self._uow.transactions.save(child)

                    transaction.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
                    await self._uow.transactions.save(transaction)
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

            result = self._build_result(successes, failures)
            await self._uow.commit()
            return result

    # -- Bulk Recover ----------------------------------------------------------

    async def bulk_recover_transactions(self, cmd: BulkRecoverTransactions) -> BulkResult:
        """Recover multiple soft-deleted transactions with partial-success semantics."""
        async with self._uow:
            # Phase 1: Request-level validation
            account = await self._load_account(cmd.account_id)
            self._verify_not_deleted(account)
            self._verify_permission(account, cmd.requesting_user_id, PermissionLevel.OWNER)
            self._validate_bulk_count(len(cmd.transaction_ids))

            # Phase 2: Per-item processing
            successes: list[BulkSuccess] = []
            failures: list[BulkFailure] = []

            for i, transaction_id in enumerate(cmd.transaction_ids):
                try:
                    transaction = await self._uow.transactions.find_by_id(
                        transaction_id, include_deleted=True
                    )
                    if transaction is None:
                        raise TransactionNotFoundError(f"Transaction {transaction_id} not found")

                    # If recovering a split child, verify parent is not deleted
                    if transaction.is_split_child():
                        parent = await self._uow.transactions.find_by_id(
                            transaction.parent_transaction_id,  # type: ignore[arg-type]
                            include_deleted=True,
                        )
                        if parent is not None and parent.is_deleted():
                            raise ParentDeletedError()

                    # Cascade recover to deleted children if split parent
                    if transaction.is_split_parent:
                        children = await self._uow.transactions.find_children(
                            transaction.id, include_deleted=True
                        )
                        for child in children:
                            if child.is_deleted():
                                child.recover()
                                await self._uow.transactions.save(child)

                    transaction.recover()
                    await self._uow.transactions.save(transaction)
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

            result = self._build_result(successes, failures)
            await self._uow.commit()
            return result

    # -- Private helpers -------------------------------------------------------

    async def _load_account(self, account_id: uuid.UUID) -> Account:
        """Load an account or raise AccountNotFoundError."""
        account = await self._uow.accounts.find_by_id(account_id, include_deleted=True)
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

import uuid

from emerald.core_finance.application.dtos.commands.account_commands import (
    CreateAccount,
    RecoverAccount,
    RenameAccount,
    SoftDeleteAccount,
    UpdateAccountNotes,
    UpdateAccountType,
    UpdateFinancialInstitution,
)
from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.exceptions import (
    AccountNameAlreadyExistsError,
    AccountNotFoundError,
    InsufficientPermissionError,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.iban import IBAN
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService


class AccountManagementService:
    """Application service orchestrating account operations."""

    def __init__(
        self,
        uow: AbstractCoreFinanceUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention_policy_service = retention_policy_service

    async def create_account(self, cmd: CreateAccount) -> Account:
        """Create a new account with all validations."""
        async with self._uow:
            owner = UserReference(user_id=cmd.owner_user_id, display_name=cmd.owner_display_name)
            currency = Currency[cmd.currency_code]
            account_name = AccountName(cmd.account_name)
            opening_balance = Money(cmd.opening_balance, currency)
            iban = IBAN(cmd.iban) if cmd.iban is not None else None

            if await self._uow.accounts.exists_by_name_for_user(account_name, cmd.owner_user_id):
                raise AccountNameAlreadyExistsError()

            account = Account.create(
                owner=owner,
                account_name=account_name,
                currency=currency,
                opening_balance=opening_balance,
                account_type_id=cmd.account_type_id,
                financial_institution_id=cmd.financial_institution_id,
                iban=iban,
                notes=cmd.notes,
            )
            await self._uow.accounts.save(account)
            await self._uow.commit()
            return account

    async def rename_account(self, cmd: RenameAccount) -> None:
        """Rename an account, checking ownership and uniqueness."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_owner(account, cmd.requesting_user_id)

            new_name = AccountName(cmd.new_name)
            owner_user_id = account.get_owner().user_id
            if await self._uow.accounts.exists_by_name_for_user(new_name, owner_user_id):
                raise AccountNameAlreadyExistsError()

            account.update_name(new_name, cmd.requesting_user_id)
            await self._uow.commit()

    async def update_account_type(self, cmd: UpdateAccountType) -> None:
        """Update account type."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_owner(account, cmd.requesting_user_id)
            account.update_account_type(cmd.account_type_id, cmd.requesting_user_id)
            await self._uow.commit()

    async def update_financial_institution(self, cmd: UpdateFinancialInstitution) -> None:
        """Update financial institution."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_owner(account, cmd.requesting_user_id)
            account.update_financial_institution(
                cmd.financial_institution_id, cmd.requesting_user_id
            )
            await self._uow.commit()

    async def update_account_notes(self, cmd: UpdateAccountNotes) -> None:
        """Update account notes."""
        async with self._uow:
            account = await self._load_account(cmd.account_id)
            self._verify_owner(account, cmd.requesting_user_id)
            account.update_notes(cmd.notes, cmd.requesting_user_id)
            await self._uow.commit()

    async def soft_delete_account(self, cmd: SoftDeleteAccount) -> None:
        """Soft-delete an account with retention period."""
        async with self._uow:
            account = await self._load_account(cmd.account_id, include_deleted=True)
            self._verify_owner(account, cmd.requesting_user_id)

            retention = await self._retention_policy_service.get_effective_retention(
                DeletableEntityType.FINANCIAL_ACCOUNT, cmd.requesting_user_id
            )
            account.soft_delete(cmd.requesting_user_id, retention, cmd.reason)
            await self._uow.commit()

    async def recover_account(self, cmd: RecoverAccount) -> None:
        """Recover a soft-deleted account."""
        async with self._uow:
            account = await self._load_account(cmd.account_id, include_deleted=True)
            self._verify_owner(account, cmd.requesting_user_id)
            account.recover()
            await self._uow.commit()

    # -- Private helpers -------------------------------------------------------

    async def _load_account(self, account_id: uuid.UUID, include_deleted: bool = False) -> Account:
        """Load an account or raise AccountNotFoundError."""
        account = await self._uow.accounts.find_by_id(account_id, include_deleted=include_deleted)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _verify_owner(self, account: Account, requesting_user_id: uuid.UUID) -> None:
        """Verify the requesting user is the account owner via share-based permission."""
        if not account.is_owner(requesting_user_id):
            raise InsufficientPermissionError(
                f"User {requesting_user_id} does not have OWNER permission on account {account.id}"
            )

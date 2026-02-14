from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.application.dtos.commands.account_commands import CreateAccount
from emerald.core_finance.application.dtos.commands.card_commands import (
    AddCard,
    LinkTransactionToCard,
    RecoverCard,
    RemoveCard,
    UnlinkTransactionFromCard,
    UpdateCardName,
)
from emerald.core_finance.application.services.account_management import (
    AccountManagementService,
)
from emerald.core_finance.application.services.card_management import (
    CardManagementService,
)
from emerald.core_finance.domain.exceptions import (
    AccountNotFoundError,
    CardNotFoundError,
    TransactionNotFoundError,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    InsufficientPermissionError,
)
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.import_source_type import ImportSourceType
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.core_finance.fakes import FakeCoreFinanceUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


def _make_services() -> tuple[
    CardManagementService, AccountManagementService, FakeCoreFinanceUnitOfWork
]:
    uow = FakeCoreFinanceUnitOfWork()
    retention_repo = FakeRetentionPolicyRepository()
    retention_service = RetentionPolicyService(preference_repository=retention_repo)
    acct_service = AccountManagementService(uow=uow, retention_policy_service=retention_service)
    card_service = CardManagementService(uow=uow, retention_policy_service=retention_service)
    return card_service, acct_service, uow


def _make_create_account_cmd(**overrides: Any) -> CreateAccount:
    defaults: dict[str, Any] = {
        "owner_user_id": uuid.uuid4(),
        "owner_display_name": "Test User",
        "account_name": "My Account",
        "currency_code": "USD",
        "opening_balance": Decimal("0"),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return CreateAccount(**defaults)


def _make_add_card_cmd(
    account_id: uuid.UUID, requesting_user_id: uuid.UUID, **overrides: Any
) -> AddCard:
    defaults: dict[str, Any] = {
        "account_id": account_id,
        "requesting_user_id": requesting_user_id,
        "card_type": "CREDIT",
        "card_name": "My Card",
        "card_number": "4111111111111111",
        "expiry_month": 12,
        "expiry_year": 2030,
    }
    defaults.update(overrides)
    return AddCard(**defaults)


def _make_transaction(
    account_id: uuid.UUID,
    created_by: uuid.UUID,
    currency: Currency = Currency.USD,
) -> Transaction:
    return Transaction.create(
        account_id=account_id,
        transaction_date=date(2024, 1, 15),
        amount=Money(Decimal("100.00"), currency),
        original_description="Test Transaction",
        created_by=created_by,
        import_source=ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        ),
    )


# ---------------------------------------------------------------------------
# TestAddCard
# ---------------------------------------------------------------------------


class TestAddCard:
    def test_adds_card_successfully(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)
        uow.committed = False

        cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(cmd)

        assert card.card_name == "My Card"
        assert card.card_type.value == "CREDIT"
        assert card.card_number.last_four == "1111"
        assert card.expiry_month == 12
        assert card.expiry_year == 2030

    def test_saves_and_commits(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)
        uow.committed = False

        cmd = _make_add_card_cmd(account.id, owner_id)
        card_service.add_card(cmd)
        assert uow.committed is True

    def test_account_not_found(self) -> None:
        card_service, _, _ = _make_services()
        cmd = _make_add_card_cmd(uuid.uuid4(), uuid.uuid4())
        with pytest.raises(AccountNotFoundError):
            card_service.add_card(cmd)

    def test_requires_editor_permission(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        random_user = uuid.uuid4()
        cmd = _make_add_card_cmd(account.id, random_user)
        with pytest.raises(InsufficientPermissionError):
            card_service.add_card(cmd)

    def test_with_credit_limit(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        cmd = _make_add_card_cmd(
            account.id,
            owner_id,
            credit_limit_amount=Decimal("5000"),
            credit_limit_currency="USD",
        )
        card = card_service.add_card(cmd)
        assert card.credit_limit is not None
        assert card.credit_limit == Money(Decimal("5000"), Currency.USD)

    def test_with_optional_fields(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        cmd = _make_add_card_cmd(
            account.id,
            owner_id,
            card_network="VISA",
            issuing_institution="Chase Bank",
            notes="Primary spending card",
        )
        card = card_service.add_card(cmd)
        assert card.card_network is not None
        assert card.card_network.value == "VISA"
        assert card.issuing_institution == "Chase Bank"
        assert card.notes == "Primary spending card"


# ---------------------------------------------------------------------------
# TestUpdateCardName
# ---------------------------------------------------------------------------


class TestUpdateCardName:
    def test_updates_name_successfully(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        update_cmd = UpdateCardName(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
            card_name="Updated Card Name",
        )
        card_service.update_card_name(update_cmd)

        # Reload account from repo to check the card
        loaded = uow.accounts.find_by_id(account.id)
        assert loaded is not None
        updated_card = loaded.get_card(card.id)
        assert updated_card is not None
        assert updated_card.card_name == "Updated Card Name"

    def test_commits_uow(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)
        uow.committed = False

        update_cmd = UpdateCardName(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
            card_name="Updated Name",
        )
        card_service.update_card_name(update_cmd)
        assert uow.committed is True

    def test_card_not_found(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        update_cmd = UpdateCardName(
            account_id=account.id,
            card_id=uuid.uuid4(),
            requesting_user_id=owner_id,
            card_name="Should Fail",
        )
        with pytest.raises(CardNotFoundError):
            card_service.update_card_name(update_cmd)


# ---------------------------------------------------------------------------
# TestRemoveCard
# ---------------------------------------------------------------------------


class TestRemoveCard:
    def test_removes_card(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.remove_card(remove_cmd)

        loaded = uow.accounts.find_by_id(account.id)
        assert loaded is not None
        # Active cards should be 0
        assert loaded.active_card_count == 0
        # Card still exists when including deleted
        deleted_card = loaded.get_card(card.id, include_deleted=True)
        assert deleted_card is not None
        assert deleted_card.is_deleted()

    def test_commits_uow(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)
        uow.committed = False

        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.remove_card(remove_cmd)
        assert uow.committed is True

    def test_card_not_found(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=uuid.uuid4(),
            requesting_user_id=owner_id,
        )
        with pytest.raises(CardNotFoundError):
            card_service.remove_card(remove_cmd)


# ---------------------------------------------------------------------------
# TestRecoverCard
# ---------------------------------------------------------------------------


class TestRecoverCard:
    def test_recovers_card(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.remove_card(remove_cmd)

        recover_cmd = RecoverCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.recover_card(recover_cmd)

        loaded = uow.accounts.find_by_id(account.id)
        assert loaded is not None
        recovered_card = loaded.get_card(card.id)
        assert recovered_card is not None
        assert not recovered_card.is_deleted()

    def test_requires_owner(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.remove_card(remove_cmd)

        random_user = uuid.uuid4()
        recover_cmd = RecoverCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=random_user,
        )
        with pytest.raises(InsufficientPermissionError):
            card_service.recover_card(recover_cmd)

    def test_commits_uow(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.remove_card(remove_cmd)
        uow.committed = False

        recover_cmd = RecoverCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.recover_card(recover_cmd)
        assert uow.committed is True


# ---------------------------------------------------------------------------
# TestLinkTransactionToCard
# ---------------------------------------------------------------------------


class TestLinkTransactionToCard:
    def test_links_transaction_to_card(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        txn = _make_transaction(account.id, owner_id)
        uow.transactions.save(txn)

        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.link_transaction_to_card(link_cmd)

        loaded_txn = uow.transactions.find_by_id(txn.id)
        assert loaded_txn is not None
        assert loaded_txn.card_id == card.id

    def test_card_not_found(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        txn = _make_transaction(account.id, owner_id)
        uow.transactions.save(txn)

        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=uuid.uuid4(),
            requesting_user_id=owner_id,
        )
        with pytest.raises(CardNotFoundError):
            card_service.link_transaction_to_card(link_cmd)

    def test_transaction_not_found(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=uuid.uuid4(),
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        with pytest.raises(TransactionNotFoundError):
            card_service.link_transaction_to_card(link_cmd)

    def test_transaction_in_different_account(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        # Create a transaction belonging to a different account
        other_account_id = uuid.uuid4()
        txn = _make_transaction(other_account_id, owner_id)
        uow.transactions.save(txn)

        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        with pytest.raises(TransactionNotFoundError):
            card_service.link_transaction_to_card(link_cmd)

    def test_commits_uow(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        txn = _make_transaction(account.id, owner_id)
        uow.transactions.save(txn)
        uow.committed = False

        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.link_transaction_to_card(link_cmd)
        assert uow.committed is True

    def test_links_to_deleted_card(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        # Soft-delete the card
        remove_cmd = RemoveCard(
            account_id=account.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.remove_card(remove_cmd)

        txn = _make_transaction(account.id, owner_id)
        uow.transactions.save(txn)

        # Should still succeed -- historical linking allowed
        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.link_transaction_to_card(link_cmd)

        loaded_txn = uow.transactions.find_by_id(txn.id)
        assert loaded_txn is not None
        assert loaded_txn.card_id == card.id


# ---------------------------------------------------------------------------
# TestUnlinkTransactionFromCard
# ---------------------------------------------------------------------------


class TestUnlinkTransactionFromCard:
    def test_unlinks_transaction(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        txn = _make_transaction(account.id, owner_id)
        uow.transactions.save(txn)

        # Link first
        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.link_transaction_to_card(link_cmd)

        # Then unlink
        unlink_cmd = UnlinkTransactionFromCard(
            account_id=account.id,
            transaction_id=txn.id,
            requesting_user_id=owner_id,
        )
        card_service.unlink_transaction_from_card(unlink_cmd)

        loaded_txn = uow.transactions.find_by_id(txn.id)
        assert loaded_txn is not None
        assert loaded_txn.card_id is None

    def test_transaction_not_found(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        unlink_cmd = UnlinkTransactionFromCard(
            account_id=account.id,
            transaction_id=uuid.uuid4(),
            requesting_user_id=owner_id,
        )
        with pytest.raises(TransactionNotFoundError):
            card_service.unlink_transaction_from_card(unlink_cmd)

    def test_commits_uow(self) -> None:
        card_service, acct_service, uow = _make_services()
        owner_id = uuid.uuid4()
        acct_cmd = _make_create_account_cmd(owner_user_id=owner_id)
        account = acct_service.create_account(acct_cmd)

        add_cmd = _make_add_card_cmd(account.id, owner_id)
        card = card_service.add_card(add_cmd)

        txn = _make_transaction(account.id, owner_id)
        uow.transactions.save(txn)

        link_cmd = LinkTransactionToCard(
            account_id=account.id,
            transaction_id=txn.id,
            card_id=card.id,
            requesting_user_id=owner_id,
        )
        card_service.link_transaction_to_card(link_cmd)
        uow.committed = False

        unlink_cmd = UnlinkTransactionFromCard(
            account_id=account.id,
            transaction_id=txn.id,
            requesting_user_id=owner_id,
        )
        card_service.unlink_transaction_from_card(unlink_cmd)
        assert uow.committed is True

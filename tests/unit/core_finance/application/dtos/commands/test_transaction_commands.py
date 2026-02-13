from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from emerald.core_finance.application.dtos.commands.transaction_commands import (
    CreateTransaction,
    RecoverTransaction,
    ReviewTransaction,
    SoftDeleteTransaction,
    UnreviewTransaction,
    UpdateTransactionAmount,
    UpdateTransactionComments,
    UpdateTransactionDates,
    UpdateTransactionDescription,
    UpdateTransactionMerchant,
)
from emerald.shared_kernel.application.dtos.commands import Command


class TestCreateTransaction:
    def test_is_command(self) -> None:
        assert issubclass(CreateTransaction, Command)

    def test_defaults(self) -> None:
        cmd = CreateTransaction()
        assert cmd.account_id == uuid.UUID(int=0)
        assert cmd.requesting_user_id == uuid.UUID(int=0)
        assert cmd.transaction_date == date(2000, 1, 1)
        assert cmd.amount == Decimal("0")
        assert cmd.currency_code == ""
        assert cmd.original_description == ""
        assert cmd.value_date is None
        assert cmd.merchant is None
        assert cmd.comments is None
        assert cmd.import_source_type == "MANUAL"
        assert cmd.source_id is None
        assert cmd.external_id is None

    def test_custom_values(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = CreateTransaction(
            account_id=aid,
            requesting_user_id=uid,
            transaction_date=date(2024, 6, 15),
            amount=Decimal("123.45"),
            currency_code="EUR",
            original_description="Coffee",
            value_date=date(2024, 6, 16),
            merchant="Starbucks",
            comments="Morning coffee",
            import_source_type="BANK_IMPORT",
            source_id="conn-abc",
            external_id="ext-001",
        )
        assert cmd.account_id == aid
        assert cmd.requesting_user_id == uid
        assert cmd.transaction_date == date(2024, 6, 15)
        assert cmd.amount == Decimal("123.45")
        assert cmd.currency_code == "EUR"
        assert cmd.original_description == "Coffee"
        assert cmd.value_date == date(2024, 6, 16)
        assert cmd.merchant == "Starbucks"
        assert cmd.comments == "Morning coffee"
        assert cmd.import_source_type == "BANK_IMPORT"
        assert cmd.source_id == "conn-abc"
        assert cmd.external_id == "ext-001"


class TestUpdateTransactionDescription:
    def test_is_command(self) -> None:
        assert issubclass(UpdateTransactionDescription, Command)

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        tid = uuid.uuid4()
        cmd = UpdateTransactionDescription(
            account_id=aid,
            requesting_user_id=uid,
            transaction_id=tid,
            user_description="Updated",
        )
        assert cmd.account_id == aid
        assert cmd.requesting_user_id == uid
        assert cmd.transaction_id == tid
        assert cmd.user_description == "Updated"

    def test_none_description(self) -> None:
        cmd = UpdateTransactionDescription(user_description=None)
        assert cmd.user_description is None


class TestUpdateTransactionMerchant:
    def test_is_command(self) -> None:
        assert issubclass(UpdateTransactionMerchant, Command)

    def test_fields(self) -> None:
        cmd = UpdateTransactionMerchant(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            merchant="New Merchant",
        )
        assert cmd.merchant == "New Merchant"

    def test_none_merchant(self) -> None:
        cmd = UpdateTransactionMerchant(merchant=None)
        assert cmd.merchant is None


class TestUpdateTransactionComments:
    def test_is_command(self) -> None:
        assert issubclass(UpdateTransactionComments, Command)

    def test_fields(self) -> None:
        cmd = UpdateTransactionComments(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            comments="A comment",
        )
        assert cmd.comments == "A comment"


class TestUpdateTransactionDates:
    def test_is_command(self) -> None:
        assert issubclass(UpdateTransactionDates, Command)

    def test_fields(self) -> None:
        cmd = UpdateTransactionDates(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            transaction_date=date(2024, 3, 1),
            value_date=date(2024, 3, 2),
        )
        assert cmd.transaction_date == date(2024, 3, 1)
        assert cmd.value_date == date(2024, 3, 2)


class TestUpdateTransactionAmount:
    def test_is_command(self) -> None:
        assert issubclass(UpdateTransactionAmount, Command)

    def test_fields(self) -> None:
        cmd = UpdateTransactionAmount(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            amount=Decimal("55.55"),
            currency_code="GBP",
        )
        assert cmd.amount == Decimal("55.55")
        assert cmd.currency_code == "GBP"


class TestReviewTransaction:
    def test_is_command(self) -> None:
        assert issubclass(ReviewTransaction, Command)

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        tid = uuid.uuid4()
        cmd = ReviewTransaction(
            account_id=aid,
            requesting_user_id=uid,
            transaction_id=tid,
        )
        assert cmd.account_id == aid
        assert cmd.requesting_user_id == uid
        assert cmd.transaction_id == tid


class TestUnreviewTransaction:
    def test_is_command(self) -> None:
        assert issubclass(UnreviewTransaction, Command)

    def test_fields(self) -> None:
        cmd = UnreviewTransaction(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
        )
        assert isinstance(cmd.transaction_id, uuid.UUID)


class TestSoftDeleteTransaction:
    def test_is_command(self) -> None:
        assert issubclass(SoftDeleteTransaction, Command)

    def test_with_reason(self) -> None:
        cmd = SoftDeleteTransaction(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            reason="Duplicate",
        )
        assert cmd.reason == "Duplicate"

    def test_without_reason(self) -> None:
        cmd = SoftDeleteTransaction(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
        )
        assert cmd.reason is None


class TestRecoverTransaction:
    def test_is_command(self) -> None:
        assert issubclass(RecoverTransaction, Command)

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        tid = uuid.uuid4()
        cmd = RecoverTransaction(
            account_id=aid,
            requesting_user_id=uid,
            transaction_id=tid,
        )
        assert cmd.account_id == aid
        assert cmd.requesting_user_id == uid
        assert cmd.transaction_id == tid

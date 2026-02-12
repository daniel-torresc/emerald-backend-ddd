import uuid
from decimal import Decimal

from emerald.core_finance.application.dtos.commands.account_commands import (
    CreateAccount,
    RecoverAccount,
    RenameAccount,
    SoftDeleteAccount,
    UpdateAccountNotes,
    UpdateAccountType,
    UpdateFinancialInstitution,
)
from emerald.shared_kernel.application.dtos.commands import Command


class TestCreateAccount:
    def test_is_command(self) -> None:
        assert issubclass(CreateAccount, Command)

    def test_fields(self) -> None:
        uid = uuid.uuid4()
        tid = uuid.uuid4()
        fid = uuid.uuid4()
        cmd = CreateAccount(
            owner_user_id=uid,
            owner_display_name="Alice",
            account_name="Checking",
            currency_code="USD",
            opening_balance=Decimal("1000.00"),
            account_type_id=tid,
            financial_institution_id=fid,
            iban="GB29NWBK60161331926819",
            notes="My account",
        )
        assert cmd.owner_user_id == uid
        assert cmd.owner_display_name == "Alice"
        assert cmd.account_name == "Checking"
        assert cmd.currency_code == "USD"
        assert cmd.opening_balance == Decimal("1000.00")
        assert cmd.account_type_id == tid
        assert cmd.financial_institution_id == fid
        assert cmd.iban == "GB29NWBK60161331926819"
        assert cmd.notes == "My account"


class TestRenameAccount:
    def test_is_command(self) -> None:
        assert issubclass(RenameAccount, Command)

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = RenameAccount(account_id=aid, requesting_user_id=uid, new_name="Savings")
        assert cmd.account_id == aid
        assert cmd.requesting_user_id == uid
        assert cmd.new_name == "Savings"


class TestUpdateAccountType:
    def test_is_command(self) -> None:
        assert issubclass(UpdateAccountType, Command)

    def test_fields(self) -> None:
        cmd = UpdateAccountType(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            account_type_id=uuid.uuid4(),
        )
        assert isinstance(cmd.account_type_id, uuid.UUID)


class TestUpdateFinancialInstitution:
    def test_is_command(self) -> None:
        assert issubclass(UpdateFinancialInstitution, Command)

    def test_fields(self) -> None:
        cmd = UpdateFinancialInstitution(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            financial_institution_id=uuid.uuid4(),
        )
        assert isinstance(cmd.financial_institution_id, uuid.UUID)


class TestUpdateAccountNotes:
    def test_is_command(self) -> None:
        assert issubclass(UpdateAccountNotes, Command)

    def test_with_notes(self) -> None:
        cmd = UpdateAccountNotes(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            notes="Hello",
        )
        assert cmd.notes == "Hello"

    def test_with_none_notes(self) -> None:
        cmd = UpdateAccountNotes(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            notes=None,
        )
        assert cmd.notes is None


class TestSoftDeleteAccount:
    def test_is_command(self) -> None:
        assert issubclass(SoftDeleteAccount, Command)

    def test_with_reason(self) -> None:
        cmd = SoftDeleteAccount(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            reason="No longer needed",
        )
        assert cmd.reason == "No longer needed"

    def test_without_reason(self) -> None:
        cmd = SoftDeleteAccount(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
        )
        assert cmd.reason is None


class TestRecoverAccount:
    def test_is_command(self) -> None:
        assert issubclass(RecoverAccount, Command)

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = RecoverAccount(account_id=aid, requesting_user_id=uid)
        assert cmd.account_id == aid
        assert cmd.requesting_user_id == uid

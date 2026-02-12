import uuid
from decimal import Decimal
from typing import Any

from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


def _make_account(**overrides: Any) -> Account:
    owner = overrides.pop("owner", UserReference(user_id=uuid.uuid4(), display_name="Test User"))
    defaults: dict[str, Any] = {
        "account_name": AccountName("Test Account"),
        "currency": Currency.USD,
        "opening_balance": Money(Decimal("1000.00"), Currency.USD),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return Account.create(owner=owner, **defaults)


class TestCalculateBalance:
    def test_returns_opening_balance(self) -> None:
        account = _make_account()
        balance = account.calculate_balance()
        assert balance == Money(Decimal("1000.00"), Currency.USD)

    def test_balance_currency_matches_account(self) -> None:
        account = _make_account(
            currency=Currency.EUR,
            opening_balance=Money(Decimal("500.00"), Currency.EUR),
        )
        assert account.calculate_balance().currency == Currency.EUR

    def test_negative_opening_balance(self) -> None:
        account = _make_account(opening_balance=Money(Decimal("-200.00"), Currency.USD))
        balance = account.calculate_balance()
        assert balance.amount == Decimal("-200.00")

    def test_zero_opening_balance(self) -> None:
        account = _make_account(opening_balance=Money(Decimal("0"), Currency.USD))
        assert account.calculate_balance().is_zero()


class TestTransactionCount:
    def test_returns_zero(self) -> None:
        account = _make_account()
        assert account.transaction_count == 0

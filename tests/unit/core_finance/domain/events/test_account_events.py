import uuid
from decimal import Decimal

from emerald.core_finance.domain.events.account_events import (
    AccountCreated,
    AccountRecovered,
    AccountSoftDeleted,
    AccountUpdated,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class TestAccountCreated:
    def test_is_domain_event(self) -> None:
        assert issubclass(AccountCreated, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert AccountCreated.aggregate_type == "account"

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = AccountCreated(
            aggregate_id=aid,
            owner_user_id=uid,
            currency_code="USD",
            account_name="Checking",
            opening_balance=Decimal("1000.00"),
        )
        assert event.aggregate_id == aid
        assert event.owner_user_id == uid
        assert event.currency_code == "USD"
        assert event.account_name == "Checking"
        assert event.opening_balance == Decimal("1000.00")


class TestAccountUpdated:
    def test_is_domain_event(self) -> None:
        assert issubclass(AccountUpdated, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert AccountUpdated.aggregate_type == "account"

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = AccountUpdated(
            aggregate_id=aid,
            updated_by=uid,
            changed_fields=frozenset({"account_name"}),
        )
        assert event.updated_by == uid
        assert event.changed_fields == frozenset({"account_name"})


class TestAccountSoftDeleted:
    def test_is_domain_event(self) -> None:
        assert issubclass(AccountSoftDeleted, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert AccountSoftDeleted.aggregate_type == "account"

    def test_fields_with_reason(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = AccountSoftDeleted(
            aggregate_id=aid,
            deleted_by=uid,
            reason="No longer needed",
        )
        assert event.deleted_by == uid
        assert event.reason == "No longer needed"

    def test_fields_without_reason(self) -> None:
        event = AccountSoftDeleted(
            aggregate_id=uuid.uuid4(),
            deleted_by=uuid.uuid4(),
        )
        assert event.reason is None


class TestAccountRecovered:
    def test_is_domain_event(self) -> None:
        assert issubclass(AccountRecovered, DomainEvent)

    def test_aggregate_type(self) -> None:
        assert AccountRecovered.aggregate_type == "account"

    def test_fields(self) -> None:
        aid = uuid.uuid4()
        uid = uuid.uuid4()
        event = AccountRecovered(
            aggregate_id=aid,
            recovered_by=uid,
        )
        assert event.recovered_by == uid

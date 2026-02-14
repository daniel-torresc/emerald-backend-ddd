import uuid

from emerald.core_finance.domain.events.transaction_events import (
    TransactionsBulkCreated,
    TransactionsBulkDeleted,
    TransactionsBulkRecovered,
    TransactionsBulkUpdated,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class TestTransactionsBulkCreated:
    def test_construction(self) -> None:
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = TransactionsBulkCreated(
            aggregate_id=uuid.uuid4(),
            account_id=account_id,
            success_count=5,
            failure_count=2,
            import_source_type="BULK_IMPORT",
            created_by=user_id,
        )
        assert event.account_id == account_id
        assert event.success_count == 5
        assert event.failure_count == 2
        assert event.import_source_type == "BULK_IMPORT"
        assert event.created_by == user_id

    def test_aggregate_type(self) -> None:
        assert TransactionsBulkCreated.aggregate_type == "transaction"

    def test_is_domain_event(self) -> None:
        event = TransactionsBulkCreated(aggregate_id=uuid.uuid4())
        assert isinstance(event, DomainEvent)

    def test_defaults(self) -> None:
        event = TransactionsBulkCreated(aggregate_id=uuid.uuid4())
        assert event.success_count == 0
        assert event.failure_count == 0
        assert event.import_source_type == ""


class TestTransactionsBulkUpdated:
    def test_construction(self) -> None:
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = TransactionsBulkUpdated(
            aggregate_id=uuid.uuid4(),
            account_id=account_id,
            success_count=3,
            failure_count=1,
            updated_fields=frozenset({"review_status", "merchant"}),
            updated_by=user_id,
        )
        assert event.account_id == account_id
        assert event.success_count == 3
        assert event.failure_count == 1
        assert event.updated_fields == frozenset({"review_status", "merchant"})
        assert event.updated_by == user_id

    def test_aggregate_type(self) -> None:
        assert TransactionsBulkUpdated.aggregate_type == "transaction"

    def test_defaults(self) -> None:
        event = TransactionsBulkUpdated(aggregate_id=uuid.uuid4())
        assert event.updated_fields == frozenset()


class TestTransactionsBulkDeleted:
    def test_construction(self) -> None:
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = TransactionsBulkDeleted(
            aggregate_id=uuid.uuid4(),
            account_id=account_id,
            success_count=4,
            failure_count=0,
            deleted_by=user_id,
        )
        assert event.account_id == account_id
        assert event.success_count == 4
        assert event.failure_count == 0
        assert event.deleted_by == user_id

    def test_aggregate_type(self) -> None:
        assert TransactionsBulkDeleted.aggregate_type == "transaction"


class TestTransactionsBulkRecovered:
    def test_construction(self) -> None:
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = TransactionsBulkRecovered(
            aggregate_id=uuid.uuid4(),
            account_id=account_id,
            success_count=2,
            failure_count=1,
            recovered_by=user_id,
        )
        assert event.account_id == account_id
        assert event.success_count == 2
        assert event.failure_count == 1
        assert event.recovered_by == user_id

    def test_aggregate_type(self) -> None:
        assert TransactionsBulkRecovered.aggregate_type == "transaction"

import uuid

from emerald.classification.domain.events.categorization_events import (
    TransactionCategorized,
    TransactionUncategorized,
)
from emerald.classification.domain.models.value_objects.uncategorization_reason import (
    UncategorizationReason,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_ZERO = uuid.UUID(int=0)


class TestTransactionCategorized:
    def test_defaults(self) -> None:
        e = TransactionCategorized(aggregate_id=_ZERO)
        assert e.aggregate_type == "transaction"
        assert e.term_id == _ZERO
        assert e.taxonomy_id == _ZERO
        assert e.assignment_id == _ZERO
        assert e.assigned_by == _ZERO
        assert e.is_reassignment is False
        assert isinstance(e, DomainEvent)

    def test_with_values(self) -> None:
        tx_id = uuid.uuid4()
        term_id = uuid.uuid4()
        tax_id = uuid.uuid4()
        assign_id = uuid.uuid4()
        user_id = uuid.uuid4()
        e = TransactionCategorized(
            aggregate_id=tx_id,
            term_id=term_id,
            taxonomy_id=tax_id,
            assignment_id=assign_id,
            assigned_by=user_id,
            is_reassignment=True,
        )
        assert e.aggregate_id == tx_id
        assert e.term_id == term_id
        assert e.taxonomy_id == tax_id
        assert e.assignment_id == assign_id
        assert e.assigned_by == user_id
        assert e.is_reassignment is True

    def test_frozen(self) -> None:
        e = TransactionCategorized(aggregate_id=_ZERO)
        import dataclasses

        assert dataclasses.is_dataclass(e)


class TestTransactionUncategorized:
    def test_defaults(self) -> None:
        e = TransactionUncategorized(aggregate_id=_ZERO)
        assert e.aggregate_type == "transaction"
        assert e.taxonomy_id == _ZERO
        assert e.term_id == _ZERO
        assert e.reason == UncategorizationReason.MANUAL
        assert isinstance(e, DomainEvent)

    def test_with_values(self) -> None:
        tx_id = uuid.uuid4()
        tax_id = uuid.uuid4()
        term_id = uuid.uuid4()
        e = TransactionUncategorized(
            aggregate_id=tx_id,
            taxonomy_id=tax_id,
            term_id=term_id,
            reason=UncategorizationReason.TERM_DELETED,
        )
        assert e.aggregate_id == tx_id
        assert e.taxonomy_id == tax_id
        assert e.term_id == term_id
        assert e.reason == UncategorizationReason.TERM_DELETED

    def test_all_reasons(self) -> None:
        for reason in UncategorizationReason:
            e = TransactionUncategorized(aggregate_id=_ZERO, reason=reason)
            assert e.reason == reason

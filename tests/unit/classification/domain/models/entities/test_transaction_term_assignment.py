import uuid
from datetime import UTC, datetime

import pytest

from emerald.classification.domain.models.entities.transaction_term_assignment import (
    TransactionTermAssignment,
)
from emerald.shared_kernel.domain.models.base.entity import Entity

_NIL = uuid.UUID(int=0)


class TestTransactionTermAssignmentFactory:
    def test_create_generates_id_and_assigned_at(self) -> None:
        tx_id, term_id, tax_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        assignment = TransactionTermAssignment.create(
            transaction_id=tx_id,
            term_id=term_id,
            taxonomy_id=tax_id,
            assigned_by=user_id,
        )
        assert assignment.transaction_id == tx_id
        assert assignment.term_id == term_id
        assert assignment.taxonomy_id == tax_id
        assert assignment.assigned_by == user_id
        assert assignment.id != _NIL
        assert assignment.assigned_at.tzinfo is not None

    def test_create_assigned_at_is_utc(self) -> None:
        assignment = TransactionTermAssignment.create(
            transaction_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            taxonomy_id=uuid.uuid4(),
            assigned_by=uuid.uuid4(),
        )
        assert assignment.assigned_at.tzinfo == UTC


class TestTransactionTermAssignmentValidation:
    def test_nil_transaction_id_raises(self) -> None:
        with pytest.raises(ValueError, match="transaction_id"):
            TransactionTermAssignment(
                transaction_id=_NIL,
                term_id=uuid.uuid4(),
                taxonomy_id=uuid.uuid4(),
                assigned_at=datetime.now(UTC),
                assigned_by=uuid.uuid4(),
            )

    def test_nil_term_id_raises(self) -> None:
        with pytest.raises(ValueError, match="term_id"):
            TransactionTermAssignment(
                transaction_id=uuid.uuid4(),
                term_id=_NIL,
                taxonomy_id=uuid.uuid4(),
                assigned_at=datetime.now(UTC),
                assigned_by=uuid.uuid4(),
            )

    def test_nil_taxonomy_id_raises(self) -> None:
        with pytest.raises(ValueError, match="taxonomy_id"):
            TransactionTermAssignment(
                transaction_id=uuid.uuid4(),
                term_id=uuid.uuid4(),
                taxonomy_id=_NIL,
                assigned_at=datetime.now(UTC),
                assigned_by=uuid.uuid4(),
            )

    def test_nil_assigned_by_raises(self) -> None:
        with pytest.raises(ValueError, match="assigned_by"):
            TransactionTermAssignment(
                transaction_id=uuid.uuid4(),
                term_id=uuid.uuid4(),
                taxonomy_id=uuid.uuid4(),
                assigned_at=datetime.now(UTC),
                assigned_by=_NIL,
            )

    def test_naive_assigned_at_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            TransactionTermAssignment(
                transaction_id=uuid.uuid4(),
                term_id=uuid.uuid4(),
                taxonomy_id=uuid.uuid4(),
                assigned_at=datetime.now(),  # noqa: DTZ005
                assigned_by=uuid.uuid4(),
            )

    def test_tz_aware_assigned_at_accepted(self) -> None:
        assignment = TransactionTermAssignment(
            transaction_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            taxonomy_id=uuid.uuid4(),
            assigned_at=datetime.now(UTC),
            assigned_by=uuid.uuid4(),
        )
        assert assignment.assigned_at.tzinfo is not None


class TestTransactionTermAssignmentIdentity:
    def test_extends_entity(self) -> None:
        assignment = TransactionTermAssignment.create(
            transaction_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            taxonomy_id=uuid.uuid4(),
            assigned_by=uuid.uuid4(),
        )
        assert isinstance(assignment, Entity)

    def test_equality_by_id(self) -> None:
        shared_id = uuid.uuid4()
        a = TransactionTermAssignment(
            id=shared_id,
            transaction_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            taxonomy_id=uuid.uuid4(),
            assigned_at=datetime.now(UTC),
            assigned_by=uuid.uuid4(),
        )
        b = TransactionTermAssignment(
            id=shared_id,
            transaction_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            taxonomy_id=uuid.uuid4(),
            assigned_at=datetime.now(UTC),
            assigned_by=uuid.uuid4(),
        )
        assert a == b

    def test_hydration_with_explicit_id(self) -> None:
        explicit_id = uuid.uuid4()
        assignment = TransactionTermAssignment(
            id=explicit_id,
            transaction_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            taxonomy_id=uuid.uuid4(),
            assigned_at=datetime.now(UTC),
            assigned_by=uuid.uuid4(),
        )
        assert assignment.id == explicit_id

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from emerald.core_finance.domain.models.entities.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import (
    ImportSource,
)
from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
)
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


def _make_transaction(**overrides: Any) -> Transaction:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "transaction_date": date(2024, 1, 15),
        "amount": Money(Decimal("100.00"), Currency.USD),
        "original_description": "Test Transaction",
        "created_by": uuid.uuid4(),
        "import_source": ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        ),
    }
    defaults.update(overrides)
    tx = Transaction.create(**defaults)
    tx.collect_events()  # clear creation events
    return tx


class TestImmutableProperties:
    def test_account_id_is_read_only(self) -> None:
        tx = _make_transaction()
        assert isinstance(type(tx).__dict__.get("account_id"), property)

    def test_original_description_is_read_only(self) -> None:
        tx = _make_transaction()
        assert isinstance(type(tx).__dict__.get("original_description"), property)

    def test_import_source_is_read_only(self) -> None:
        tx = _make_transaction()
        assert isinstance(type(tx).__dict__.get("import_source"), property)

    def test_external_id_is_read_only(self) -> None:
        tx = _make_transaction()
        assert isinstance(type(tx).__dict__.get("external_id"), property)

    def test_parent_transaction_id_is_read_only(self) -> None:
        tx = _make_transaction()
        assert isinstance(type(tx).__dict__.get("parent_transaction_id"), property)

    def test_created_by_is_read_only(self) -> None:
        # created_by comes from AuditableMixin
        tx = _make_transaction()
        assert tx.created_by is not None
        # Verify it's a property on the mixin class
        from emerald.shared_kernel.domain.models.base.auditable import (
            AuditableMixin,
        )

        assert isinstance(AuditableMixin.__dict__.get("created_by"), property)


class TestEffectiveDescription:
    def test_returns_user_description_when_set(self) -> None:
        tx = _make_transaction(original_description="Bank: Direct Debit")
        tx.update_description("My Rent Payment", uuid.uuid4())
        assert tx.effective_description == "My Rent Payment"

    def test_returns_original_when_user_description_none(self) -> None:
        tx = _make_transaction(original_description="Bank: Direct Debit")
        assert tx.user_description is None
        assert tx.effective_description == "Bank: Direct Debit"

    def test_original_description_unchanged_after_update(self) -> None:
        tx = _make_transaction(original_description="Bank: Direct Debit")
        tx.update_description("My override", uuid.uuid4())
        assert tx.original_description == "Bank: Direct Debit"


class TestSplitStubs:
    def test_is_split_parent_returns_false(self) -> None:
        tx = _make_transaction()
        assert tx.is_split_parent is False

    def test_is_split_child_true_when_parent_set(self) -> None:
        parent_id = uuid.uuid4()
        tx = _make_transaction(parent_transaction_id=parent_id)
        assert tx.is_split_child() is True

    def test_is_split_child_false_when_no_parent(self) -> None:
        tx = _make_transaction()
        assert tx.is_split_child() is False

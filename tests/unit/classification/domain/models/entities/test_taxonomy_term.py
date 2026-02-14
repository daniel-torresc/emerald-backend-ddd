import uuid

import pytest

from emerald.classification.domain.models.entities.taxonomy_term import TaxonomyTerm
from emerald.classification.domain.models.value_objects import TermName
from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


def _make_term(**overrides: object) -> TaxonomyTerm:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "taxonomy_id": uuid.uuid4(),
        "name": TermName("Food"),
        "description": None,
        "parent_term_id": None,
        "sort_order": 0,
    }
    defaults.update(overrides)
    return TaxonomyTerm(**defaults)  # type: ignore[arg-type]


class TestTaxonomyTermConstruction:
    def test_create_root_term(self) -> None:
        tid = uuid.uuid4()
        tax_id = uuid.uuid4()
        term = TaxonomyTerm(id=tid, taxonomy_id=tax_id, name=TermName("Food"))
        assert term.id == tid
        assert term.taxonomy_id == tax_id
        assert term.name == TermName("Food")
        assert term.description is None
        assert term.parent_term_id is None
        assert term.sort_order == 0

    def test_create_child_term(self) -> None:
        parent_id = uuid.uuid4()
        term = _make_term(parent_term_id=parent_id, sort_order=2, description="A desc")
        assert term.parent_term_id == parent_id
        assert term.sort_order == 2
        assert term.description == "A desc"

    def test_taxonomy_id_is_property(self) -> None:
        tax_id = uuid.uuid4()
        term = _make_term(taxonomy_id=tax_id)
        assert term.taxonomy_id == tax_id


class TestTaxonomyTermMutations:
    def test_rename(self) -> None:
        term = _make_term()
        old_updated = term.updated_at
        term._rename(TermName("Restaurants"))
        assert term.name == TermName("Restaurants")
        assert term.updated_at >= old_updated

    def test_update_description(self) -> None:
        term = _make_term()
        term._update_description("New desc")
        assert term.description == "New desc"

    def test_update_description_to_none(self) -> None:
        term = _make_term(description="Old")
        term._update_description(None)
        assert term.description is None

    def test_move(self) -> None:
        term = _make_term()
        new_parent = uuid.uuid4()
        term._move(new_parent)
        assert term.parent_term_id == new_parent

    def test_move_to_root(self) -> None:
        parent_id = uuid.uuid4()
        term = _make_term(parent_term_id=parent_id)
        term._move(None)
        assert term.parent_term_id is None

    def test_set_sort_order(self) -> None:
        term = _make_term(sort_order=0)
        term._set_sort_order(5)
        assert term.sort_order == 5


class TestTaxonomyTermSoftDelete:
    def test_soft_delete(self) -> None:
        term = _make_term()
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        term.soft_delete(deleted_by=uuid.uuid4(), retention=retention)
        assert term.is_deleted()
        assert not term.is_active()

    def test_recover(self) -> None:
        term = _make_term()
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        term.soft_delete(deleted_by=uuid.uuid4(), retention=retention)
        term.recover()
        assert term.is_active()

    def test_double_delete_raises(self) -> None:
        term = _make_term()
        retention = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)
        term.soft_delete(deleted_by=uuid.uuid4(), retention=retention)
        with pytest.raises(AlreadyDeletedError):
            term.soft_delete(deleted_by=uuid.uuid4(), retention=retention)

    def test_recover_active_raises(self) -> None:
        term = _make_term()
        with pytest.raises(NotDeletedError):
            term.recover()


class TestTaxonomyTermTimestamps:
    def test_created_at_set(self) -> None:
        term = _make_term()
        assert term.created_at is not None

    def test_updated_at_set(self) -> None:
        term = _make_term()
        assert term.updated_at is not None
        assert term.updated_at >= term.created_at

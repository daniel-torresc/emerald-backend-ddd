import uuid
from typing import Any

import pytest

from emerald.classification.domain.constants import (
    MAX_TAXONOMY_DESCRIPTION_LENGTH,
    MAX_TERM_DESCRIPTION_LENGTH,
    MAX_TERMS_PER_TAXONOMY,
)
from emerald.classification.domain.events import (
    TaxonomyCreated,
    TaxonomyDescriptionUpdated,
    TaxonomyRecovered,
    TaxonomyRenamed,
    TaxonomySoftDeleted,
    TermAdded,
    TermDeleted,
    TermDescriptionUpdated,
    TermMoved,
    TermRecovered,
    TermRenamed,
    TermsReordered,
)
from emerald.classification.domain.exceptions import (
    CannotBeOwnParentError,
    CircularReferenceError,
    IncompleteReorderError,
    MaxTermsExceededError,
    ParentTermDeletedError,
    ParentTermNotFoundError,
    TaxonomyDescriptionTooLongError,
    TaxonomyNotActiveError,
    TermDescriptionTooLongError,
    TermNameAlreadyExistsError,
    TermNotFoundError,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.value_objects import TaxonomyName, TermName
from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)

_RETENTION = RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


def _make_taxonomy(**overrides: Any) -> Taxonomy:
    defaults: dict[str, Any] = {
        "owner_id": uuid.uuid4(),
        "name": TaxonomyName("Categories"),
    }
    defaults.update(overrides)
    return Taxonomy.create(**defaults)


# =============================================================================
# Creation
# =============================================================================


class TestTaxonomyCreation:
    def test_create_basic(self) -> None:
        owner = uuid.uuid4()
        t = Taxonomy.create(owner_id=owner, name=TaxonomyName("Budget"))
        assert t.owner_id == owner
        assert t.name == TaxonomyName("Budget")
        assert t.description is None
        assert t.active_term_count == 0
        assert t.version == 1

    def test_create_with_description(self) -> None:
        t = _make_taxonomy(description="My spending categories")
        assert t.description == "My spending categories"

    def test_create_description_too_long(self) -> None:
        with pytest.raises(TaxonomyDescriptionTooLongError):
            _make_taxonomy(description="x" * (MAX_TAXONOMY_DESCRIPTION_LENGTH + 1))

    def test_create_emits_event(self) -> None:
        t = _make_taxonomy()
        events = t.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TaxonomyCreated)
        assert events[0].aggregate_id == t.id
        assert events[0].owner_id == t.owner_id
        assert events[0].name == t.name.value

    def test_created_by_equals_owner(self) -> None:
        owner = uuid.uuid4()
        t = Taxonomy.create(owner_id=owner, name=TaxonomyName("X"))
        assert t.created_by == owner


# =============================================================================
# Updates
# =============================================================================


class TestTaxonomyUpdates:
    def test_rename(self) -> None:
        t = _make_taxonomy()
        t.collect_events()
        t.rename(TaxonomyName("New Name"))
        assert t.name == TaxonomyName("New Name")
        events = t.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TaxonomyRenamed)

    def test_rename_deleted_raises(self) -> None:
        t = _make_taxonomy()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        with pytest.raises(TaxonomyNotActiveError):
            t.rename(TaxonomyName("X"))

    def test_update_description(self) -> None:
        t = _make_taxonomy()
        t.collect_events()
        t.update_description("New desc")
        assert t.description == "New desc"
        events = t.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], TaxonomyDescriptionUpdated)

    def test_update_description_to_none(self) -> None:
        t = _make_taxonomy(description="Old")
        t.collect_events()
        t.update_description(None)
        assert t.description is None

    def test_update_description_too_long(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TaxonomyDescriptionTooLongError):
            t.update_description("x" * (MAX_TAXONOMY_DESCRIPTION_LENGTH + 1))

    def test_update_description_deleted_raises(self) -> None:
        t = _make_taxonomy()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        with pytest.raises(TaxonomyNotActiveError):
            t.update_description("X")


# =============================================================================
# Lifecycle
# =============================================================================


class TestTaxonomyLifecycle:
    def test_soft_delete(self) -> None:
        t = _make_taxonomy()
        t.collect_events()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        assert t.is_deleted()

    def test_soft_delete_cascades_terms(self) -> None:
        t = _make_taxonomy()
        t.add_term(TermName("A"))
        t.add_term(TermName("B"))
        t.collect_events()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        for term in t.terms:
            assert term.is_deleted()
        events = t.collect_events()
        sd_events = [e for e in events if isinstance(e, TaxonomySoftDeleted)]
        assert len(sd_events) == 1
        assert sd_events[0].term_count == 2

    def test_soft_delete_already_deleted_raises(self) -> None:
        t = _make_taxonomy()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        with pytest.raises(AlreadyDeletedError):
            t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)

    def test_recover(self) -> None:
        t = _make_taxonomy()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        t.collect_events()
        t.recover()
        assert t.is_active()
        events = t.collect_events()
        assert any(isinstance(e, TaxonomyRecovered) for e in events)

    def test_recover_does_not_recover_terms(self) -> None:
        t = _make_taxonomy()
        t.add_term(TermName("A"))
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        t.recover()
        assert t.is_active()
        # Terms remain deleted
        assert all(term.is_deleted() for term in t.terms)

    def test_recover_not_deleted_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(NotDeletedError):
            t.recover()


# =============================================================================
# Add Term
# =============================================================================


class TestAddTerm:
    def test_add_root_term(self) -> None:
        t = _make_taxonomy()
        t.collect_events()
        term = t.add_term(TermName("Food"))
        assert term.name == TermName("Food")
        assert term.parent_term_id is None
        assert term.sort_order == 0
        assert t.active_term_count == 1

    def test_add_child_term(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("Food"))
        child = t.add_term(TermName("Restaurants"), parent_term_id=parent.id)
        assert child.parent_term_id == parent.id

    def test_add_term_with_description(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"), description="All food expenses")
        assert term.description == "All food expenses"

    def test_add_term_name_uniqueness_case_insensitive(self) -> None:
        t = _make_taxonomy()
        t.add_term(TermName("Food"))
        with pytest.raises(TermNameAlreadyExistsError):
            t.add_term(TermName("food"))

    def test_add_term_name_uniqueness_across_parents(self) -> None:
        t = _make_taxonomy()
        parent_a = t.add_term(TermName("A"))
        t.add_term(TermName("X"), parent_term_id=parent_a.id)
        parent_b = t.add_term(TermName("B"))
        with pytest.raises(TermNameAlreadyExistsError):
            t.add_term(TermName("X"), parent_term_id=parent_b.id)

    def test_add_term_deleted_taxonomy_raises(self) -> None:
        t = _make_taxonomy()
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        with pytest.raises(TaxonomyNotActiveError):
            t.add_term(TermName("X"))

    def test_add_term_deleted_parent_raises(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("Food"))
        t.delete_term(parent.id, deleted_by=t.owner_id)
        with pytest.raises(ParentTermDeletedError):
            t.add_term(TermName("New"), parent_term_id=parent.id)

    def test_add_term_parent_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(ParentTermNotFoundError):
            t.add_term(TermName("X"), parent_term_id=uuid.uuid4())

    def test_add_term_max_terms_exceeded(self) -> None:
        t = _make_taxonomy()
        for i in range(MAX_TERMS_PER_TAXONOMY):
            t.add_term(TermName(f"Term{i}"))
        with pytest.raises(MaxTermsExceededError):
            t.add_term(TermName("Overflow"))

    def test_add_term_auto_sort_order(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"))
        c = t.add_term(TermName("C"))
        assert a.sort_order == 0
        assert b.sort_order == 1
        assert c.sort_order == 2

    def test_add_term_emits_event(self) -> None:
        t = _make_taxonomy()
        t.collect_events()
        term = t.add_term(TermName("Food"))
        events = t.collect_events()
        added = [e for e in events if isinstance(e, TermAdded)]
        assert len(added) == 1
        assert added[0].term_id == term.id
        assert added[0].name == "Food"

    def test_add_term_description_too_long(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermDescriptionTooLongError):
            t.add_term(TermName("X"), description="x" * (MAX_TERM_DESCRIPTION_LENGTH + 1))


# =============================================================================
# Rename Term
# =============================================================================


class TestRenameTerm:
    def test_rename_term(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Old"))
        t.collect_events()
        t.rename_term(term.id, TermName("New"))
        assert term.name == TermName("New")
        events = t.collect_events()
        renamed = [e for e in events if isinstance(e, TermRenamed)]
        assert len(renamed) == 1
        assert renamed[0].old_name == "Old"
        assert renamed[0].new_name == "New"

    def test_rename_term_not_found(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.rename_term(uuid.uuid4(), TermName("X"))

    def test_rename_term_name_conflict(self) -> None:
        t = _make_taxonomy()
        t.add_term(TermName("A"))
        b = t.add_term(TermName("B"))
        with pytest.raises(TermNameAlreadyExistsError):
            t.rename_term(b.id, TermName("a"))

    def test_rename_term_same_name_allowed(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        t.collect_events()
        t.rename_term(term.id, TermName("FOOD"))
        assert term.name == TermName("FOOD")


# =============================================================================
# Update Term Description
# =============================================================================


class TestUpdateTermDescription:
    def test_update_term_description(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        t.collect_events()
        t.update_term_description(term.id, "Desc")
        assert term.description == "Desc"
        events = t.collect_events()
        assert any(isinstance(e, TermDescriptionUpdated) for e in events)

    def test_update_term_description_too_long(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        with pytest.raises(TermDescriptionTooLongError):
            t.update_term_description(term.id, "x" * (MAX_TERM_DESCRIPTION_LENGTH + 1))

    def test_update_term_description_not_found(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.update_term_description(uuid.uuid4(), "X")


# =============================================================================
# Move Term
# =============================================================================


class TestMoveTerm:
    def test_move_to_new_parent(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"))
        t.collect_events()
        t.move_term(b.id, new_parent_id=a.id)
        assert b.parent_term_id == a.id
        events = t.collect_events()
        moved = [e for e in events if isinstance(e, TermMoved)]
        assert len(moved) == 1
        assert moved[0].old_parent_id is None
        assert moved[0].new_parent_id == a.id

    def test_move_to_root(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        t.collect_events()
        t.move_term(b.id, new_parent_id=None)
        assert b.parent_term_id is None

    def test_move_same_parent_no_op(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        t.collect_events()
        old_version = t.version
        t.move_term(b.id, new_parent_id=a.id)
        assert t.version == old_version  # No change
        assert len(t.collect_events()) == 0

    def test_move_self_parent_raises(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        with pytest.raises(CannotBeOwnParentError):
            t.move_term(a.id, new_parent_id=a.id)

    def test_move_creates_cycle_raises(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        c = t.add_term(TermName("C"), parent_term_id=b.id)
        with pytest.raises(CircularReferenceError):
            t.move_term(a.id, new_parent_id=c.id)

    def test_move_deep_cycle_detection(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        c = t.add_term(TermName("C"), parent_term_id=b.id)
        d = t.add_term(TermName("D"), parent_term_id=c.id)
        with pytest.raises(CircularReferenceError):
            t.move_term(a.id, new_parent_id=d.id)

    def test_move_sibling_no_cycle(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        t.add_term(TermName("B"), parent_term_id=a.id)
        e = t.add_term(TermName("E"))
        t.move_term(a.id, new_parent_id=e.id)  # Should work fine
        assert a.parent_term_id == e.id

    def test_move_parent_not_found_raises(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        with pytest.raises(ParentTermNotFoundError):
            t.move_term(a.id, new_parent_id=uuid.uuid4())

    def test_move_sort_order_at_end(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        t.add_term(TermName("B"), parent_term_id=a.id)
        t.add_term(TermName("C"), parent_term_id=a.id)
        d = t.add_term(TermName("D"))
        t.move_term(d.id, new_parent_id=a.id)
        assert d.sort_order == 2  # After B(0) and C(1)

    def test_move_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.move_term(uuid.uuid4(), new_parent_id=None)


# =============================================================================
# Delete Term
# =============================================================================


class TestDeleteTerm:
    def test_delete_term(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        t.collect_events()
        t.delete_term(term.id, deleted_by=t.owner_id)
        assert term.is_deleted()
        events = t.collect_events()
        deleted = [e for e in events if isinstance(e, TermDeleted)]
        assert len(deleted) == 1
        assert deleted[0].descendants_deleted == 0

    def test_delete_term_cascades_descendants(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        c = t.add_term(TermName("C"), parent_term_id=b.id)
        t.collect_events()
        t.delete_term(a.id, deleted_by=t.owner_id)
        assert a.is_deleted()
        assert b.is_deleted()
        assert c.is_deleted()
        events = t.collect_events()
        deleted = [e for e in events if isinstance(e, TermDeleted)]
        assert deleted[0].descendants_deleted == 2

    def test_delete_term_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.delete_term(uuid.uuid4(), deleted_by=t.owner_id)

    def test_delete_term_already_deleted_raises(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        t.delete_term(term.id, deleted_by=t.owner_id)
        with pytest.raises(AlreadyDeletedError):
            t.delete_term(term.id, deleted_by=t.owner_id)


# =============================================================================
# Recover Term
# =============================================================================


class TestRecoverTerm:
    def test_recover_term(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        t.delete_term(term.id, deleted_by=t.owner_id)
        t.collect_events()
        t.recover_term(term.id)
        assert term.is_active()
        events = t.collect_events()
        assert any(isinstance(e, TermRecovered) for e in events)

    def test_recover_term_not_deleted_raises(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        with pytest.raises(NotDeletedError):
            t.recover_term(term.id)

    def test_recover_term_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.recover_term(uuid.uuid4())

    def test_recover_term_taxonomy_not_active_raises(self) -> None:
        t = _make_taxonomy()
        term = t.add_term(TermName("Food"))
        t.soft_delete(deleted_by=t.owner_id, retention=_RETENTION)
        with pytest.raises(TaxonomyNotActiveError):
            t.recover_term(term.id)

    def test_recover_term_parent_deleted_raises(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("A"))
        child = t.add_term(TermName("B"), parent_term_id=parent.id)
        # Delete parent (cascades to child)
        t.delete_term(parent.id, deleted_by=t.owner_id)
        # Both are deleted; try to recover child while parent is still deleted
        with pytest.raises(ParentTermDeletedError):
            t.recover_term(child.id)

    def test_recover_does_not_recover_children(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("A"))
        child = t.add_term(TermName("B"), parent_term_id=parent.id)
        t.delete_term(parent.id, deleted_by=t.owner_id)
        t.recover_term(parent.id)
        assert parent.is_active()
        assert child.is_deleted()  # Children remain deleted


# =============================================================================
# Reorder Terms
# =============================================================================


class TestReorderTerms:
    def test_reorder(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"))
        c = t.add_term(TermName("C"))
        t.collect_events()
        t.reorder_terms([c.id, a.id, b.id])
        assert c.sort_order == 0
        assert a.sort_order == 1
        assert b.sort_order == 2
        events = t.collect_events()
        reordered = [e for e in events if isinstance(e, TermsReordered)]
        assert len(reordered) == 1
        assert reordered[0].ordered_term_ids == (c.id, a.id, b.id)

    def test_reorder_children(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("P"))
        a = t.add_term(TermName("A"), parent_term_id=parent.id)
        b = t.add_term(TermName("B"), parent_term_id=parent.id)
        t.collect_events()
        t.reorder_terms([b.id, a.id], parent_id=parent.id)
        assert b.sort_order == 0
        assert a.sort_order == 1

    def test_reorder_incomplete_raises(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        t.add_term(TermName("B"))
        with pytest.raises(IncompleteReorderError):
            t.reorder_terms([a.id])

    def test_reorder_duplicates_raises(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        with pytest.raises(IncompleteReorderError):
            t.reorder_terms([a.id, a.id])

    def test_reorder_wrong_parent_raises(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        p = t.add_term(TermName("P"))
        b = t.add_term(TermName("B"), parent_term_id=p.id)
        with pytest.raises(TermNotFoundError):
            t.reorder_terms([a.id, b.id])  # b is not a root sibling


# =============================================================================
# Query Methods
# =============================================================================


class TestQueryMethods:
    def test_get_root_terms_sorted(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"))
        c = t.add_term(TermName("C"))
        roots = t.get_root_terms()
        assert [r.id for r in roots] == [a.id, b.id, c.id]

    def test_get_children_sorted(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("P"))
        a = t.add_term(TermName("A"), parent_term_id=parent.id)
        b = t.add_term(TermName("B"), parent_term_id=parent.id)
        children = t.get_children(parent.id)
        assert [c.id for c in children] == [a.id, b.id]

    def test_get_children_excludes_deleted(self) -> None:
        t = _make_taxonomy()
        parent = t.add_term(TermName("P"))
        a = t.add_term(TermName("A"), parent_term_id=parent.id)
        b = t.add_term(TermName("B"), parent_term_id=parent.id)
        t.delete_term(a.id, deleted_by=t.owner_id)
        children = t.get_children(parent.id)
        assert [c.id for c in children] == [b.id]

    def test_get_descendants_recursive(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        c = t.add_term(TermName("C"), parent_term_id=b.id)
        d = t.add_term(TermName("D"), parent_term_id=a.id)
        descendants = t.get_descendants(a.id)
        assert len(descendants) == 3
        # Depth-first: B, C, D
        assert descendants[0].id == b.id
        assert descendants[1].id == c.id
        assert descendants[2].id == d.id

    def test_get_term_path(self) -> None:
        t = _make_taxonomy()
        food = t.add_term(TermName("Food"))
        restaurants = t.add_term(TermName("Restaurants"), parent_term_id=food.id)
        italian = t.add_term(TermName("Italian"), parent_term_id=restaurants.id)
        path = t.get_term_path(italian.id)
        assert str(path) == "Food > Restaurants > Italian"
        assert path.depth == 2

    def test_get_term_path_root(self) -> None:
        t = _make_taxonomy()
        food = t.add_term(TermName("Food"))
        path = t.get_term_path(food.id)
        assert str(path) == "Food"
        assert path.depth == 0

    def test_get_term_path_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.get_term_path(uuid.uuid4())

    def test_get_term_depth(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        b = t.add_term(TermName("B"), parent_term_id=a.id)
        c = t.add_term(TermName("C"), parent_term_id=b.id)
        assert t.get_term_depth(a.id) == 0
        assert t.get_term_depth(b.id) == 1
        assert t.get_term_depth(c.id) == 2

    def test_get_term_depth_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.get_term_depth(uuid.uuid4())

    def test_active_term_count(self) -> None:
        t = _make_taxonomy()
        assert t.active_term_count == 0
        a = t.add_term(TermName("A"))
        assert t.active_term_count == 1
        t.add_term(TermName("B"))
        assert t.active_term_count == 2
        t.delete_term(a.id, deleted_by=t.owner_id)
        assert t.active_term_count == 1

    def test_find_term(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        assert t.find_term(a.id) == a
        assert t.find_term(uuid.uuid4()) is None

    def test_get_term(self) -> None:
        t = _make_taxonomy()
        a = t.add_term(TermName("A"))
        assert t.get_term(a.id) == a

    def test_get_term_not_found_raises(self) -> None:
        t = _make_taxonomy()
        with pytest.raises(TermNotFoundError):
            t.get_term(uuid.uuid4())

    def test_terms_returns_all(self) -> None:
        t = _make_taxonomy()
        t.add_term(TermName("A"))
        b = t.add_term(TermName("B"))
        t.delete_term(b.id, deleted_by=t.owner_id)
        all_terms = t.terms
        assert len(all_terms) == 2

    def test_version_increments(self) -> None:
        t = _make_taxonomy()
        v = t.version
        t.add_term(TermName("A"))
        assert t.version == v + 1
        t.rename(TaxonomyName("New"))
        assert t.version == v + 2

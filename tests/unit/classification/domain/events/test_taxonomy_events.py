import uuid

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
from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_ZERO = uuid.UUID(int=0)


class TestTaxonomyEvents:
    def test_taxonomy_created_defaults(self) -> None:
        e = TaxonomyCreated(aggregate_id=_ZERO)
        assert e.aggregate_type == "Taxonomy"
        assert e.owner_id == _ZERO
        assert e.name == ""
        assert isinstance(e, DomainEvent)

    def test_taxonomy_created_with_values(self) -> None:
        tid = uuid.uuid4()
        oid = uuid.uuid4()
        e = TaxonomyCreated(aggregate_id=tid, owner_id=oid, name="Budget")
        assert e.aggregate_id == tid
        assert e.owner_id == oid
        assert e.name == "Budget"

    def test_taxonomy_renamed(self) -> None:
        e = TaxonomyRenamed(aggregate_id=_ZERO, old_name="A", new_name="B")
        assert e.aggregate_type == "Taxonomy"
        assert e.old_name == "A"
        assert e.new_name == "B"

    def test_taxonomy_description_updated(self) -> None:
        e = TaxonomyDescriptionUpdated(aggregate_id=_ZERO)
        assert e.aggregate_type == "Taxonomy"

    def test_taxonomy_soft_deleted(self) -> None:
        uid = uuid.uuid4()
        e = TaxonomySoftDeleted(aggregate_id=_ZERO, deleted_by=uid, term_count=5)
        assert e.deleted_by == uid
        assert e.term_count == 5

    def test_taxonomy_recovered(self) -> None:
        e = TaxonomyRecovered(aggregate_id=_ZERO)
        assert e.aggregate_type == "Taxonomy"


class TestTermEvents:
    def test_term_added(self) -> None:
        tid = uuid.uuid4()
        pid = uuid.uuid4()
        e = TermAdded(aggregate_id=_ZERO, term_id=tid, name="Food", parent_term_id=pid)
        assert e.term_id == tid
        assert e.name == "Food"
        assert e.parent_term_id == pid

    def test_term_added_root(self) -> None:
        e = TermAdded(aggregate_id=_ZERO, name="Food")
        assert e.parent_term_id is None

    def test_term_renamed(self) -> None:
        e = TermRenamed(aggregate_id=_ZERO, old_name="A", new_name="B")
        assert e.old_name == "A"
        assert e.new_name == "B"

    def test_term_description_updated(self) -> None:
        tid = uuid.uuid4()
        e = TermDescriptionUpdated(aggregate_id=_ZERO, term_id=tid)
        assert e.term_id == tid

    def test_term_moved(self) -> None:
        tid = uuid.uuid4()
        old_pid = uuid.uuid4()
        new_pid = uuid.uuid4()
        e = TermMoved(aggregate_id=_ZERO, term_id=tid, old_parent_id=old_pid, new_parent_id=new_pid)
        assert e.term_id == tid
        assert e.old_parent_id == old_pid
        assert e.new_parent_id == new_pid

    def test_term_deleted(self) -> None:
        e = TermDeleted(aggregate_id=_ZERO, descendants_deleted=3)
        assert e.descendants_deleted == 3

    def test_term_recovered(self) -> None:
        tid = uuid.uuid4()
        e = TermRecovered(aggregate_id=_ZERO, term_id=tid)
        assert e.term_id == tid

    def test_terms_reordered(self) -> None:
        ids = (uuid.uuid4(), uuid.uuid4())
        e = TermsReordered(aggregate_id=_ZERO, ordered_term_ids=ids)
        assert e.ordered_term_ids == ids
        assert e.parent_id is None

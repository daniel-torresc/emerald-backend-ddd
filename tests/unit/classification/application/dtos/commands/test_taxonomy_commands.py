import uuid

from emerald.classification.application.dtos.commands import (
    AddTerm,
    CreateTaxonomy,
    DeleteTerm,
    MoveTerm,
    RecoverTaxonomy,
    RecoverTerm,
    RenameTaxonomy,
    RenameTerm,
    ReorderTerms,
    SoftDeleteTaxonomy,
    UpdateTaxonomyDescription,
    UpdateTermDescription,
)


class TestTaxonomyCommands:
    def test_create_taxonomy_defaults(self) -> None:
        cmd = CreateTaxonomy()
        assert cmd.owner_id == uuid.UUID(int=0)
        assert cmd.name == ""
        assert cmd.description is None

    def test_create_taxonomy_with_values(self) -> None:
        oid = uuid.uuid4()
        cmd = CreateTaxonomy(owner_id=oid, name="Budget", description="Desc")
        assert cmd.owner_id == oid
        assert cmd.name == "Budget"
        assert cmd.description == "Desc"

    def test_rename_taxonomy(self) -> None:
        cmd = RenameTaxonomy(taxonomy_id=uuid.uuid4(), owner_id=uuid.uuid4(), new_name="New")
        assert cmd.new_name == "New"

    def test_update_taxonomy_description(self) -> None:
        cmd = UpdateTaxonomyDescription(description="Desc")
        assert cmd.description == "Desc"

    def test_soft_delete_taxonomy(self) -> None:
        cmd = SoftDeleteTaxonomy(taxonomy_id=uuid.uuid4(), owner_id=uuid.uuid4())
        assert cmd.taxonomy_id != uuid.UUID(int=0)

    def test_recover_taxonomy(self) -> None:
        cmd = RecoverTaxonomy()
        assert cmd.taxonomy_id == uuid.UUID(int=0)


class TestTermCommands:
    def test_add_term(self) -> None:
        pid = uuid.uuid4()
        cmd = AddTerm(name="Food", parent_term_id=pid, description="Desc")
        assert cmd.name == "Food"
        assert cmd.parent_term_id == pid

    def test_add_term_defaults(self) -> None:
        cmd = AddTerm()
        assert cmd.parent_term_id is None
        assert cmd.description is None

    def test_rename_term(self) -> None:
        cmd = RenameTerm(term_id=uuid.uuid4(), new_name="New")
        assert cmd.new_name == "New"

    def test_update_term_description(self) -> None:
        cmd = UpdateTermDescription(description="Desc")
        assert cmd.description == "Desc"

    def test_move_term(self) -> None:
        pid = uuid.uuid4()
        cmd = MoveTerm(new_parent_id=pid)
        assert cmd.new_parent_id == pid

    def test_move_term_to_root(self) -> None:
        cmd = MoveTerm()
        assert cmd.new_parent_id is None

    def test_delete_term(self) -> None:
        cmd = DeleteTerm(term_id=uuid.uuid4())
        assert cmd.term_id != uuid.UUID(int=0)

    def test_recover_term(self) -> None:
        cmd = RecoverTerm()
        assert cmd.term_id == uuid.UUID(int=0)

    def test_reorder_terms(self) -> None:
        ids = [uuid.uuid4(), uuid.uuid4()]
        cmd = ReorderTerms(term_ids=ids)
        assert cmd.term_ids == ids
        assert cmd.parent_id is None

    def test_reorder_terms_defaults(self) -> None:
        cmd = ReorderTerms()
        assert cmd.term_ids == []

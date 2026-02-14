import uuid

from emerald.classification.application.dtos.commands.taxonomy_commands import (
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
from emerald.classification.application.ports.outbound.unit_of_work import (
    AbstractClassificationUnitOfWork,
)
from emerald.classification.domain.exceptions import (
    TaxonomyNameAlreadyExistsError,
    TaxonomyNotFoundError,
)
from emerald.classification.domain.models.aggregates.taxonomy import Taxonomy
from emerald.classification.domain.models.entities.taxonomy_term import TaxonomyTerm
from emerald.classification.domain.models.value_objects.taxonomy_name import TaxonomyName
from emerald.classification.domain.models.value_objects.term_name import TermName
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService


class TaxonomyManagementService:
    """Application service orchestrating taxonomy and term operations."""

    def __init__(
        self,
        uow: AbstractClassificationUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention_policy_service = retention_policy_service

    # -- Taxonomy operations ---------------------------------------------------

    def create_taxonomy(self, cmd: CreateTaxonomy) -> Taxonomy:
        with self._uow:
            name = TaxonomyName(cmd.name)
            if self._uow.taxonomies.exists_by_name_for_owner(name, cmd.owner_id):
                raise TaxonomyNameAlreadyExistsError()
            taxonomy = Taxonomy.create(
                owner_id=cmd.owner_id,
                name=name,
                description=cmd.description,
            )
            self._uow.taxonomies.save(taxonomy)
            self._uow.commit()
            return taxonomy

    def rename_taxonomy(self, cmd: RenameTaxonomy) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            new_name = TaxonomyName(cmd.new_name)
            if self._uow.taxonomies.exists_by_name_for_owner(
                new_name, cmd.owner_id, exclude_taxonomy_id=cmd.taxonomy_id
            ):
                raise TaxonomyNameAlreadyExistsError()
            taxonomy.rename(new_name)
            self._uow.commit()

    def update_taxonomy_description(self, cmd: UpdateTaxonomyDescription) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.update_description(cmd.description)
            self._uow.commit()

    def soft_delete_taxonomy(self, cmd: SoftDeleteTaxonomy) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id, include_deleted=True)
            self._verify_ownership(taxonomy, cmd.owner_id)
            retention = self._retention_policy_service.get_effective_retention(
                DeletableEntityType.TAXONOMY, cmd.owner_id
            )
            taxonomy.soft_delete(cmd.owner_id, retention)
            self._uow.commit()

    def recover_taxonomy(self, cmd: RecoverTaxonomy) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id, include_deleted=True)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.recover()
            self._uow.commit()

    # -- Term operations -------------------------------------------------------

    def add_term(self, cmd: AddTerm) -> TaxonomyTerm:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            name = TermName(cmd.name)
            term = taxonomy.add_term(
                name=name,
                parent_term_id=cmd.parent_term_id,
                description=cmd.description,
            )
            self._uow.commit()
            return term

    def rename_term(self, cmd: RenameTerm) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            new_name = TermName(cmd.new_name)
            taxonomy.rename_term(cmd.term_id, new_name)
            self._uow.commit()

    def update_term_description(self, cmd: UpdateTermDescription) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.update_term_description(cmd.term_id, cmd.description)
            self._uow.commit()

    def move_term(self, cmd: MoveTerm) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.move_term(cmd.term_id, cmd.new_parent_id)
            self._uow.commit()

    def delete_term(self, cmd: DeleteTerm) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.delete_term(cmd.term_id, deleted_by=cmd.owner_id)
            self._uow.commit()

    def recover_term(self, cmd: RecoverTerm) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.recover_term(cmd.term_id)
            self._uow.commit()

    def reorder_terms(self, cmd: ReorderTerms) -> None:
        with self._uow:
            taxonomy = self._load_taxonomy(cmd.taxonomy_id)
            self._verify_ownership(taxonomy, cmd.owner_id)
            taxonomy.reorder_terms(cmd.term_ids, cmd.parent_id)
            self._uow.commit()

    # -- Queries ---------------------------------------------------------------

    def get_taxonomy(self, taxonomy_id: uuid.UUID, owner_id: uuid.UUID) -> Taxonomy:
        with self._uow:
            taxonomy = self._load_taxonomy(taxonomy_id)
            self._verify_ownership(taxonomy, owner_id)
            return taxonomy

    def list_taxonomies(self, owner_id: uuid.UUID) -> list[Taxonomy]:
        with self._uow:
            return self._uow.taxonomies.find_by_owner(owner_id)

    # -- Private helpers -------------------------------------------------------

    def _load_taxonomy(self, taxonomy_id: uuid.UUID, include_deleted: bool = False) -> Taxonomy:
        taxonomy = self._uow.taxonomies.find_by_id(taxonomy_id, include_deleted=include_deleted)
        if taxonomy is None:
            raise TaxonomyNotFoundError(f"Taxonomy {taxonomy_id} not found")
        return taxonomy

    def _verify_ownership(self, taxonomy: Taxonomy, owner_id: uuid.UUID) -> None:
        if taxonomy.owner_id != owner_id:
            raise TaxonomyNotFoundError(f"Taxonomy {taxonomy.id} not found")

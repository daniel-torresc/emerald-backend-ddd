from abc import abstractmethod

from emerald.classification.application.ports.outbound.taxonomy_repository import TaxonomyRepository
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractClassificationUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the Classification bounded context."""

    taxonomies: TaxonomyRepository

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

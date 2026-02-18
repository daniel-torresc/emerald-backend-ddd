from abc import abstractmethod

from emerald.classification.application.ports.outbound.assignment_repository import (
    TransactionTermAssignmentRepository,
)
from emerald.classification.application.ports.outbound.taxonomy_repository import TaxonomyRepository
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractClassificationUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the Classification bounded context."""

    taxonomies: TaxonomyRepository
    assignments: TransactionTermAssignmentRepository

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

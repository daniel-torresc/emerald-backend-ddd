from abc import abstractmethod

from emerald.iam.application.ports.outbound.user_repository import UserRepository
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractIamUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the IAM bounded context."""

    users: UserRepository

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

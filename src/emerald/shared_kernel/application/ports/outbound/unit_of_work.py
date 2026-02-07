from abc import ABC, abstractmethod
from collections.abc import Iterator

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class AbstractUnitOfWork(ABC):
    """Base Unit of Work — manages transaction boundaries.

    Usage:
        with uow:
            entity = uow.some_repo.find_by_id(...)
            entity.do_something()
            uow.some_repo.add(new_entity)
            uow.commit()
    """

    def __enter__(self) -> "AbstractUnitOfWork":
        return self

    def __exit__(self, *args: object) -> None:
        self.rollback()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

    def collect_new_events(self) -> Iterator[DomainEvent]:
        """Harvest domain events from tracked aggregates. Override in subclasses."""
        return iter([])

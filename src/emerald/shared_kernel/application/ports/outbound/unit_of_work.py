from abc import ABC, abstractmethod


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

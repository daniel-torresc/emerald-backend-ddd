from abc import ABC, abstractmethod
from typing import Self


class AbstractUnitOfWork(ABC):
    """Base Unit of Work — manages transaction boundaries.

    Usage:
        async with uow:
            entity = uow.some_repo.find_by_id(...)
            entity.do_something()
            uow.some_repo.add(new_entity)
            await uow.commit()
    """

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

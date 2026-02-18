from abc import abstractmethod

from emerald.iam.application.ports.outbound.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from emerald.iam.application.ports.outbound.refresh_token_repository import RefreshTokenRepository
from emerald.iam.application.ports.outbound.user_repository import UserRepository
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractIamUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the IAM bounded context."""

    users: UserRepository
    refresh_tokens: RefreshTokenRepository
    password_reset_tokens: PasswordResetTokenRepository

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

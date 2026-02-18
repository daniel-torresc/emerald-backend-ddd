from __future__ import annotations

from emerald.iam.application.dtos.commands import ProvisionSuperadmin
from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.exceptions import (
    EmailAlreadyExistsError,
    SuperadminAlreadyExistsError,
    UsernameAlreadyExistsError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.username import Username
from emerald.iam.domain.ports.password_hasher import PasswordHasher
from emerald.iam.domain.services.password_validation import validate_password_strength


class SuperadminProvisioningService:
    """Application service for provisioning the SUPERADMIN account.

    This is called from a CLI command or installation script, never from an API.
    """

    def __init__(self, uow: AbstractIamUnitOfWork, hasher: PasswordHasher) -> None:
        self._uow = uow
        self._hasher = hasher

    async def provision_superadmin(self, cmd: ProvisionSuperadmin) -> User:
        """Create the SUPERADMIN user during platform installation."""
        async with self._uow:
            # 1. Validate password strength
            validate_password_strength(cmd.password)

            # 2. Check no SUPERADMIN exists
            if self._uow.users.exists_by_role(SystemRole.SUPERADMIN):
                raise SuperadminAlreadyExistsError()

            # 3. Validate email/username format + uniqueness
            email = EmailAddress(cmd.email)
            username = Username(cmd.username)

            if self._uow.users.exists_by_email(email):
                raise EmailAlreadyExistsError(f"Email {email} is already in use")
            if self._uow.users.exists_by_username(username):
                raise UsernameAlreadyExistsError(f"Username {username} is already taken")

            # 4. Hash password
            hashed = self._hasher.hash(cmd.password)

            # 5. Create user via superadmin factory
            user = User.provision_as_superadmin(email, username, HashedPassword(hashed))

            # 6. Persist
            self._uow.users.add(user)
            await self._uow.commit()

            return user

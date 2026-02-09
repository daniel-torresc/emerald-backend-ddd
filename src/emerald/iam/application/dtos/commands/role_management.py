from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class PromoteToAdmin(Command):
    """Command to promote a USER to ADMIN with specified permissions."""

    user_id: str
    permissions: list[str]
    promoted_by_id: str


@dataclass(frozen=True)
class DemoteToUser(Command):
    """Command to demote an ADMIN to USER."""

    user_id: str
    demoted_by_id: str


@dataclass(frozen=True)
class GrantAdminPermission(Command):
    """Command to grant an admin permission to an ADMIN user."""

    user_id: str
    permission: str
    granted_by_id: str


@dataclass(frozen=True)
class RevokeAdminPermission(Command):
    """Command to revoke an admin permission from an ADMIN user."""

    user_id: str
    permission: str
    revoked_by_id: str


@dataclass(frozen=True)
class ProvisionSuperadmin(Command):
    """Command to provision the SUPERADMIN account during installation."""

    email: str
    username: str
    password: str

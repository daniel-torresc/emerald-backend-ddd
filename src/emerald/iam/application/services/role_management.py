from __future__ import annotations

import uuid

from emerald.iam.application.dtos.commands import (
    DemoteToUser,
    GrantAdminPermission,
    PromoteToAdmin,
    RevokeAdminPermission,
)
from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.exceptions import InsufficientPermissionsError
from emerald.iam.domain.models.value_objects.admin_permission import (
    AdminPermission,
    AdminPermissionType,
)
from emerald.shared_kernel.domain.exceptions import NotFoundError


class RoleManagementService:
    """Application service for role promotion/demotion and permission management."""

    def __init__(self, uow: AbstractIamUnitOfWork) -> None:
        self._uow = uow

    async def promote_to_admin(self, cmd: PromoteToAdmin) -> None:
        """Promote a USER to ADMIN with specified permissions."""
        async with self._uow:
            actor_id = uuid.UUID(cmd.promoted_by_id)
            target_id = uuid.UUID(cmd.user_id)

            if actor_id == target_id:
                raise InsufficientPermissionsError("Cannot promote yourself")

            actor = self._uow.users.find_by_id(actor_id)
            if actor is None:
                raise NotFoundError("Actor user not found")

            target = self._uow.users.find_by_id(target_id)
            if target is None:
                raise NotFoundError("Target user not found")

            permissions = {AdminPermission(AdminPermissionType(p)) for p in cmd.permissions}
            target.promote_to_admin(permissions, actor.system_role, actor.id)
            await self._uow.commit()

    async def demote_to_user(self, cmd: DemoteToUser) -> None:
        """Demote an ADMIN to USER."""
        async with self._uow:
            actor_id = uuid.UUID(cmd.demoted_by_id)
            target_id = uuid.UUID(cmd.user_id)

            if actor_id == target_id:
                raise InsufficientPermissionsError("Cannot demote yourself")

            actor = self._uow.users.find_by_id(actor_id)
            if actor is None:
                raise NotFoundError("Actor user not found")

            target = self._uow.users.find_by_id(target_id)
            if target is None:
                raise NotFoundError("Target user not found")

            target.demote_to_user(actor.system_role, actor.id)
            await self._uow.commit()

    async def grant_admin_permission(self, cmd: GrantAdminPermission) -> None:
        """Grant an admin permission to an ADMIN user."""
        async with self._uow:
            actor_id = uuid.UUID(cmd.granted_by_id)
            target_id = uuid.UUID(cmd.user_id)

            if actor_id == target_id:
                raise InsufficientPermissionsError("Cannot grant permissions to yourself")

            actor = self._uow.users.find_by_id(actor_id)
            if actor is None:
                raise NotFoundError("Actor user not found")

            if not actor.system_role.is_admin_or_above():
                raise InsufficientPermissionsError("Only ADMIN or SUPERADMIN can grant permissions")

            permission = AdminPermission(AdminPermissionType(cmd.permission))
            has_perm = actor.has_admin_permission(permission)

            target = self._uow.users.find_by_id(target_id)
            if target is None:
                raise NotFoundError("Target user not found")

            target.grant_admin_permission(permission, actor.system_role, actor.id, has_perm)
            await self._uow.commit()

    async def revoke_admin_permission(self, cmd: RevokeAdminPermission) -> None:
        """Revoke an admin permission from an ADMIN user."""
        async with self._uow:
            actor_id = uuid.UUID(cmd.revoked_by_id)
            target_id = uuid.UUID(cmd.user_id)

            if actor_id == target_id:
                raise InsufficientPermissionsError("Cannot revoke permissions from yourself")

            actor = self._uow.users.find_by_id(actor_id)
            if actor is None:
                raise NotFoundError("Actor user not found")

            target = self._uow.users.find_by_id(target_id)
            if target is None:
                raise NotFoundError("Target user not found")

            permission = AdminPermission(AdminPermissionType(cmd.permission))
            target.revoke_admin_permission(permission, actor.system_role, actor.id)
            await self._uow.commit()

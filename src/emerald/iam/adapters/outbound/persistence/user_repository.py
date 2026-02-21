"""SQLAlchemy implementation of the UserRepository protocol."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from emerald.iam.adapters.outbound.persistence.orm_models import (
    UserAuthProviderModel,
    UserModel,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.username import Username


class SqlAlchemyUserRepository:
    """UserRepository backed by SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        user_model = UserModel.from_domain(user)

        # Sync auth provider rows by provider_type
        existing_rows = (
            (
                await self._session.execute(
                    sa.select(UserAuthProviderModel).where(UserAuthProviderModel.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )

        existing_by_type: dict[str, UserAuthProviderModel] = {
            row.provider_type: row for row in existing_rows
        }

        domain_provider_types = {p.provider_type.value for p in user.auth_providers}

        # Build synced provider list
        synced_providers: list[UserAuthProviderModel] = []
        for provider in user.auth_providers:
            pt = provider.provider_type.value
            if pt in existing_by_type:
                existing = existing_by_type[pt]
                existing.external_id = provider.external_id
                existing.linked_at = provider.linked_at
                synced_providers.append(existing)
            else:
                synced_providers.append(UserAuthProviderModel.from_domain(user.id, provider))

        # Delete removed providers
        for pt, row in existing_by_type.items():
            if pt not in domain_provider_types:
                await self._session.delete(row)

        user_model.auth_providers = synced_providers
        await self._session.merge(user_model)

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            sa.select(UserModel)
            .where(UserModel.id == user_id)
            .options(selectinload(UserModel.auth_providers))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def find_by_email(self, email: EmailAddress) -> User | None:
        stmt = (
            sa.select(UserModel)
            .where(sa.func.lower(UserModel.email) == email.value.lower())
            .options(selectinload(UserModel.auth_providers))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def find_by_username(self, username: Username) -> User | None:
        stmt = (
            sa.select(UserModel)
            .where(sa.func.lower(UserModel.username) == username.value.lower())
            .options(selectinload(UserModel.auth_providers))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model is not None else None

    async def exists_by_email(self, email: EmailAddress) -> bool:
        stmt = sa.select(sa.exists().where(sa.func.lower(UserModel.email) == email.value.lower()))
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def exists_by_username(
        self, username: Username, include_recently_deleted: bool = True
    ) -> bool:
        conditions = [sa.func.lower(UserModel.username) == username.value.lower()]
        if not include_recently_deleted:
            conditions.append(UserModel.deleted_at.is_(None))
        stmt = sa.select(sa.exists().where(sa.and_(*conditions)))
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def exists_by_role(self, role: SystemRole) -> bool:
        stmt = sa.select(sa.exists().where(UserModel.system_role == role.value))
        result = await self._session.execute(stmt)
        return bool(result.scalar())

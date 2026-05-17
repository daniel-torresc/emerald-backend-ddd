"""IAM container — auth adapters and application services."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from dependency_injector import containers, providers

from emerald.iam.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher
from emerald.iam.adapters.outbound.auth.jwt_token_service import JwtTokenService
from emerald.iam.adapters.outbound.auth.oidc_provider import OidcProviderAdapter
from emerald.iam.adapters.outbound.persistence.unit_of_work import SqlAlchemyIamUnitOfWork
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.application.services.role_management import RoleManagementService
from emerald.iam.application.services.superadmin_provisioning import (
    SuperadminProvisioningService,
)
from emerald.iam.application.services.user_registration import UserRegistrationService


async def init_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Async resource: create httpx client on startup, close on shutdown."""
    client = httpx.AsyncClient()
    yield client
    await client.aclose()


class IamContainer(containers.DeclarativeContainer):
    """IAM bounded context providers."""

    core = providers.DependenciesContainer()

    # --- Adapters (singletons — stateless or config-only) ---

    password_hasher = providers.Singleton(Argon2PasswordHasher)

    jwt_token_service = providers.Singleton(
        JwtTokenService,
        settings=core.settings.provided.jwt,
    )

    http_client: providers.Resource[httpx.AsyncClient] = providers.Resource(init_http_client)

    oidc_provider = providers.Singleton(
        OidcProviderAdapter,
        settings=core.settings.provided.oidc,
        http_client=http_client,
    )

    # --- Unit of Work (factory — new instance per use) ---

    uow = providers.Factory(
        SqlAlchemyIamUnitOfWork,
        session_factory=core.session_factory,
    )

    # --- Application services (factory — new instance per use) ---

    authentication_service = providers.Factory(
        AuthenticationService,
        uow=uow,
        hasher=password_hasher,
        token_service=jwt_token_service,
        oidc_provider=oidc_provider,
    )

    user_registration_service = providers.Factory(
        UserRegistrationService,
        uow=uow,
        hasher=password_hasher,
    )

    role_management_service = providers.Factory(
        RoleManagementService,
        uow=uow,
    )

    superadmin_provisioning_service = providers.Factory(
        SuperadminProvisioningService,
        uow=uow,
        hasher=password_hasher,
    )

"""Smoke tests for the DI composition root."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from dependency_injector import providers

from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.application.services.role_management import RoleManagementService
from emerald.iam.application.services.superadmin_provisioning import (
    SuperadminProvisioningService,
)
from emerald.iam.application.services.user_registration import UserRegistrationService
from emerald.shared_kernel.infrastructure.containers import ApplicationContainer


class TestApplicationContainer:
    """Verify container instantiation and provider resolution."""

    def test_application_container_instantiates(self) -> None:
        container = ApplicationContainer()
        assert container is not None
        assert container.core is not None
        assert container.iam is not None

    def test_core_settings_resolves(self) -> None:
        """Settings singleton resolves when env vars are set."""
        container = ApplicationContainer()
        container.core.settings.override(providers.Object(MagicMock()))
        settings = container.core.settings()
        assert settings is not None

    def test_iam_services_resolve(self) -> None:
        """IAM services resolve when DB/network deps are overridden."""
        container = ApplicationContainer()

        # Override infrastructure providers that need real connections
        mock_session_factory = MagicMock()
        mock_settings = MagicMock()

        container.core.engine.override(providers.Object(MagicMock()))
        container.core.session_factory.override(providers.Object(mock_session_factory))
        container.core.settings.override(providers.Object(mock_settings))
        container.iam.http_client.override(providers.Object(MagicMock()))

        # Resolve IAM services
        auth_svc = container.iam.authentication_service()
        reg_svc = container.iam.user_registration_service()
        role_svc = container.iam.role_management_service()
        sa_svc = container.iam.superadmin_provisioning_service()

        assert isinstance(auth_svc, AuthenticationService)
        assert isinstance(reg_svc, UserRegistrationService)
        assert isinstance(role_svc, RoleManagementService)
        assert isinstance(sa_svc, SuperadminProvisioningService)

    def test_provider_override_for_testing(self) -> None:
        """Override a provider with a fake and verify injection."""
        container = ApplicationContainer()

        # Override all infra deps
        container.core.engine.override(providers.Object(MagicMock()))
        container.core.session_factory.override(providers.Object(MagicMock()))
        container.core.settings.override(providers.Object(MagicMock()))
        container.iam.http_client.override(providers.Object(MagicMock()))

        # Override hasher with a fake
        fake_hasher = AsyncMock()
        container.iam.password_hasher.override(providers.Object(fake_hasher))

        # The service should receive the fake hasher
        reg_svc = container.iam.user_registration_service()
        assert reg_svc._hasher is fake_hasher

    def test_factory_providers_return_new_instances(self) -> None:
        """Factory providers create a new instance each call."""
        container = ApplicationContainer()

        container.core.engine.override(providers.Object(MagicMock()))
        container.core.session_factory.override(providers.Object(MagicMock()))
        container.core.settings.override(providers.Object(MagicMock()))
        container.iam.http_client.override(providers.Object(MagicMock()))

        svc1 = container.iam.authentication_service()
        svc2 = container.iam.authentication_service()
        assert svc1 is not svc2

    def test_singleton_providers_return_same_instance(self) -> None:
        """Singleton providers return the same instance."""
        container = ApplicationContainer()

        container.core.engine.override(providers.Object(MagicMock()))
        container.core.session_factory.override(providers.Object(MagicMock()))
        container.core.settings.override(providers.Object(MagicMock()))
        container.iam.http_client.override(providers.Object(MagicMock()))

        hasher1 = container.iam.password_hasher()
        hasher2 = container.iam.password_hasher()
        assert hasher1 is hasher2

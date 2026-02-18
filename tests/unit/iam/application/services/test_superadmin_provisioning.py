import uuid
from typing import Any

import pytest

from emerald.iam.application.dtos.commands import ProvisionSuperadmin
from emerald.iam.application.services.superadmin_provisioning import SuperadminProvisioningService
from emerald.iam.domain.events.role_events import SuperadminProvisioned
from emerald.iam.domain.exceptions import (
    EmailAlreadyExistsError,
    PasswordTooWeakError,
    SuperadminAlreadyExistsError,
    UsernameAlreadyExistsError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasher


def _make_user(**overrides: Any) -> User:
    defaults: dict[str, Any] = {
        "email": EmailAddress(f"user{uuid.uuid4().hex[:6]}@example.com"),
        "username": Username(f"user{uuid.uuid4().hex[:6]}"),
        "password": HashedPassword("hashed:Password1!"),
        "status": UserStatus.ACTIVE,
        "email_verified": True,
        "id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_superadmin(**overrides: Any) -> User:
    user = _make_user(**overrides)
    user.system_role = SystemRole.SUPERADMIN
    return user


def _setup() -> tuple[FakeIamUnitOfWork, FakePasswordHasher, SuperadminProvisioningService]:
    uow = FakeIamUnitOfWork()
    hasher = FakePasswordHasher()
    svc = SuperadminProvisioningService(uow, hasher)
    return uow, hasher, svc


# ---------------------------------------------------------------------------
# provision_superadmin
# ---------------------------------------------------------------------------


async def test_provision_superadmin_happy_path():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )
    user = await svc.provision_superadmin(cmd)

    assert user.system_role == SystemRole.SUPERADMIN
    assert user.status == UserStatus.ACTIVE
    assert user.email_verified is True
    assert str(user.email) == "superadmin@example.com"
    assert str(user.username) == "superadmin"


async def test_provision_superadmin_password_is_hashed():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )
    user = await svc.provision_superadmin(cmd)

    assert user.password is not None
    assert user.password.hashed_value == "hashed:StrongP@ss1!"


async def test_provision_superadmin_admin_permissions_is_none():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )
    user = await svc.provision_superadmin(cmd)

    assert user.admin_permissions is None


async def test_provision_superadmin_records_event():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )
    user = await svc.provision_superadmin(cmd)

    events = user.collect_events()
    provisioned_events = [e for e in events if isinstance(e, SuperadminProvisioned)]
    assert len(provisioned_events) >= 1
    assert provisioned_events[-1].aggregate_id == user.id


async def test_provision_superadmin_user_persisted():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )
    user = await svc.provision_superadmin(cmd)

    stored = uow.users.find_by_id(user.id)
    assert stored is not None
    assert stored.system_role == SystemRole.SUPERADMIN


async def test_provision_superadmin_weak_password_raises():
    _, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="weak",
    )

    with pytest.raises(PasswordTooWeakError):
        await svc.provision_superadmin(cmd)


async def test_provision_superadmin_already_exists_raises():
    uow, _, svc = _setup()
    existing = _make_superadmin(
        email=EmailAddress("existing@example.com"),
        username=Username("existing"),
    )
    uow.users.add(existing)

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )

    with pytest.raises(SuperadminAlreadyExistsError):
        await svc.provision_superadmin(cmd)


async def test_provision_superadmin_duplicate_email_raises():
    uow, _, svc = _setup()
    existing = _make_user(email=EmailAddress("taken@example.com"))
    uow.users.add(existing)

    cmd = ProvisionSuperadmin(
        email="taken@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )

    with pytest.raises(EmailAlreadyExistsError):
        await svc.provision_superadmin(cmd)


async def test_provision_superadmin_duplicate_username_raises():
    uow, _, svc = _setup()
    existing = _make_user(username=Username("superadmin"))
    uow.users.add(existing)

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )

    with pytest.raises(UsernameAlreadyExistsError):
        await svc.provision_superadmin(cmd)


async def test_provision_superadmin_commits_uow():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="StrongP@ss1!",
    )
    await svc.provision_superadmin(cmd)

    assert uow.committed is True


async def test_provision_superadmin_not_committed_on_failure():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="weak",
    )

    with pytest.raises(PasswordTooWeakError):
        await svc.provision_superadmin(cmd)

    assert uow.committed is False


async def test_provision_superadmin_returns_user_with_correct_email():
    uow, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="admin@emerald.io",
        username="emeraldadmin",
        password="StrongP@ss1!",
    )
    user = await svc.provision_superadmin(cmd)

    assert str(user.email) == "admin@emerald.io"
    assert str(user.username) == "emeraldadmin"


async def test_provision_superadmin_password_no_digits_raises():
    _, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="NoDigitsHere!",
    )

    with pytest.raises(PasswordTooWeakError):
        await svc.provision_superadmin(cmd)


async def test_provision_superadmin_password_no_special_char_raises():
    _, _, svc = _setup()

    cmd = ProvisionSuperadmin(
        email="superadmin@example.com",
        username="superadmin",
        password="NoSpecial123",
    )

    with pytest.raises(PasswordTooWeakError):
        await svc.provision_superadmin(cmd)

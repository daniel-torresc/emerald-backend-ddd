import uuid
from typing import Any

import pytest

from emerald.iam.domain.models.value_objects.authenticated_identity import AuthenticatedIdentity
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.system_role import SystemRole


def _make_identity(**overrides: Any) -> AuthenticatedIdentity:
    """Build a valid AuthenticatedIdentity with sensible defaults."""
    defaults: dict[str, Any] = {
        "user_id": uuid.uuid4(),
        "email": EmailAddress("user@example.com"),
        "display_name": "Test User",
        "system_role": SystemRole.USER,
    }
    defaults.update(overrides)
    return AuthenticatedIdentity(**defaults)


class TestAuthenticatedIdentityConstruction:
    def test_construction_with_all_fields(self):
        uid = uuid.uuid4()
        email = EmailAddress("alice@example.com")
        identity = AuthenticatedIdentity(
            user_id=uid,
            email=email,
            display_name="Alice",
            system_role=SystemRole.ADMIN,
        )
        assert identity.user_id == uid
        assert identity.email == email
        assert identity.display_name == "Alice"
        assert identity.system_role == SystemRole.ADMIN


class TestAuthenticatedIdentityEquality:
    def test_same_user_id_are_equal(self):
        uid = uuid.uuid4()
        identity_a = AuthenticatedIdentity(
            user_id=uid,
            email=EmailAddress("a@example.com"),
            display_name="Alice",
            system_role=SystemRole.USER,
        )
        identity_b = AuthenticatedIdentity(
            user_id=uid,
            email=EmailAddress("b@example.com"),
            display_name="Bob",
            system_role=SystemRole.ADMIN,
        )
        assert identity_a == identity_b

    def test_different_user_id_are_not_equal(self):
        identity_a = _make_identity(user_id=uuid.uuid4())
        identity_b = _make_identity(user_id=uuid.uuid4())
        assert identity_a != identity_b

    def test_hashable_by_user_id(self):
        uid = uuid.uuid4()
        identity_a = AuthenticatedIdentity(
            user_id=uid,
            email=EmailAddress("a@example.com"),
            display_name="Alice",
            system_role=SystemRole.USER,
        )
        identity_b = AuthenticatedIdentity(
            user_id=uid,
            email=EmailAddress("b@example.com"),
            display_name="Bob",
            system_role=SystemRole.ADMIN,
        )
        identity_set = {identity_a, identity_b}
        assert len(identity_set) == 1

    def test_different_user_ids_in_set(self):
        identity_a = _make_identity(user_id=uuid.uuid4())
        identity_b = _make_identity(user_id=uuid.uuid4())
        identity_set = {identity_a, identity_b}
        assert len(identity_set) == 2


class TestAuthenticatedIdentityImmutability:
    def test_frozen(self):
        identity = _make_identity()
        with pytest.raises(AttributeError):
            identity.display_name = "Changed"  # type: ignore[misc]

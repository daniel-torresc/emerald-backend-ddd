import uuid

import pytest

from emerald.core_finance.domain.exceptions import InvalidUserReferenceError
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.iam.domain.models.value_objects.authenticated_identity import AuthenticatedIdentity
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.system_role import SystemRole


class TestUserReferenceCreation:
    def test_valid_creation(self) -> None:
        uid = uuid.uuid4()
        ref = UserReference(user_id=uid, display_name="Alice")
        assert ref.user_id == uid
        assert ref.display_name == "Alice"

    def test_rejects_none_user_id(self) -> None:
        with pytest.raises(InvalidUserReferenceError):
            UserReference(user_id=None, display_name="Alice")  # type: ignore[arg-type]

    def test_rejects_empty_display_name(self) -> None:
        with pytest.raises(InvalidUserReferenceError):
            UserReference(user_id=uuid.uuid4(), display_name="")

    def test_rejects_whitespace_only_display_name(self) -> None:
        with pytest.raises(InvalidUserReferenceError):
            UserReference(user_id=uuid.uuid4(), display_name="   ")

    def test_frozen(self) -> None:
        ref = UserReference(user_id=uuid.uuid4(), display_name="Alice")
        with pytest.raises(AttributeError):
            ref.display_name = "Bob"  # type: ignore[misc]

    def test_equality(self) -> None:
        uid = uuid.uuid4()
        ref1 = UserReference(user_id=uid, display_name="Alice")
        ref2 = UserReference(user_id=uid, display_name="Alice")
        assert ref1 == ref2

    def test_inequality_different_id(self) -> None:
        ref1 = UserReference(user_id=uuid.uuid4(), display_name="Alice")
        ref2 = UserReference(user_id=uuid.uuid4(), display_name="Alice")
        assert ref1 != ref2


class TestUserReferenceFromIdentity:
    def test_translates_correctly(self) -> None:
        uid = uuid.uuid4()
        identity = AuthenticatedIdentity(
            user_id=uid,
            email=EmailAddress("alice@example.com"),
            display_name="Alice",
            system_role=SystemRole.ADMIN,
        )
        ref = UserReference.from_identity(identity)
        assert ref.user_id == uid
        assert ref.display_name == "Alice"

    def test_discards_email_and_role(self) -> None:
        uid = uuid.uuid4()
        identity = AuthenticatedIdentity(
            user_id=uid,
            email=EmailAddress("alice@example.com"),
            display_name="Alice",
            system_role=SystemRole.SUPERADMIN,
        )
        ref = UserReference.from_identity(identity)
        assert not hasattr(ref, "email")
        assert not hasattr(ref, "system_role")

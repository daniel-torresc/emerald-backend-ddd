import uuid

from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.username import Username


class TestUserSystemRole:
    def test_new_user_has_user_role(self):
        user = User.register(
            email=EmailAddress("test@example.com"),
            username=Username("testuser"),
            hashed_password=HashedPassword("hashed:password"),
        )
        assert user.system_role == SystemRole.USER

    def test_system_role_is_accessible(self):
        user = User.register(
            email=EmailAddress("test@example.com"),
            username=Username("testuser"),
            hashed_password=HashedPassword("hashed:password"),
        )
        role = user.system_role
        assert isinstance(role, SystemRole)

    def test_reconstructed_user_accepts_admin_role(self):
        uid = uuid.uuid4()
        user = User(
            email=EmailAddress("admin@example.com"),
            username=Username("adminuser"),
            password=HashedPassword("hashed:password"),
            system_role=SystemRole.ADMIN,
            id=uid,
            created_by=uid,
        )
        assert user.system_role == SystemRole.ADMIN

    def test_reconstructed_user_accepts_superadmin_role(self):
        uid = uuid.uuid4()
        user = User(
            email=EmailAddress("super@example.com"),
            username=Username("superuser"),
            password=HashedPassword("hashed:password"),
            system_role=SystemRole.SUPERADMIN,
            id=uid,
            created_by=uid,
        )
        assert user.system_role == SystemRole.SUPERADMIN

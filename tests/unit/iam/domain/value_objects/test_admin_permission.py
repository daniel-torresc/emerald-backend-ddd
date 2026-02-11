import pytest

from emerald.iam.domain.models.value_objects.admin_permission import (
    AdminPermission,
    AdminPermissionType,
)

# -- Creation ------------------------------------------------------------------


class TestAdminPermissionCreation:
    def test_create_with_master_data_admin(self):
        perm = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        assert perm.value == AdminPermissionType.MASTER_DATA_ADMIN

    def test_create_with_user_support_admin(self):
        perm = AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)
        assert perm.value == AdminPermissionType.USER_SUPPORT_ADMIN

    def test_create_with_compliance_admin(self):
        perm = AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)
        assert perm.value == AdminPermissionType.COMPLIANCE_ADMIN

    def test_create_with_full_admin(self):
        perm = AdminPermission(AdminPermissionType.FULL_ADMIN)
        assert perm.value == AdminPermissionType.FULL_ADMIN

    def test_invalid_type_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected AdminPermissionType"):
            AdminPermission("NOT_A_TYPE")  # type: ignore[arg-type]

    def test_invalid_type_none_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected AdminPermissionType"):
            AdminPermission(None)  # type: ignore[arg-type]

    def test_frozen_cannot_modify(self):
        perm = AdminPermission(AdminPermissionType.FULL_ADMIN)
        with pytest.raises(AttributeError):
            perm.value = AdminPermissionType.MASTER_DATA_ADMIN  # type: ignore[misc]


# -- Equality ------------------------------------------------------------------


class TestAdminPermissionEquality:
    def test_same_value_is_equal(self):
        a = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        b = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        assert a == b

    def test_different_value_is_not_equal(self):
        a = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        b = AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)
        assert a != b


# -- includes() ----------------------------------------------------------------


class TestAdminPermissionIncludes:
    def test_full_admin_includes_master_data(self):
        full = AdminPermission(AdminPermissionType.FULL_ADMIN)
        master = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        assert full.includes(master) is True

    def test_full_admin_includes_user_support(self):
        full = AdminPermission(AdminPermissionType.FULL_ADMIN)
        support = AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)
        assert full.includes(support) is True

    def test_full_admin_includes_compliance(self):
        full = AdminPermission(AdminPermissionType.FULL_ADMIN)
        compliance = AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)
        assert full.includes(compliance) is True

    def test_full_admin_includes_itself(self):
        full = AdminPermission(AdminPermissionType.FULL_ADMIN)
        assert full.includes(full) is True

    def test_master_data_does_not_include_full_admin(self):
        master = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        full = AdminPermission(AdminPermissionType.FULL_ADMIN)
        assert master.includes(full) is False

    def test_master_data_does_not_include_user_support(self):
        master = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        support = AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)
        assert master.includes(support) is False

    def test_master_data_includes_itself(self):
        master = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
        assert master.includes(AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)) is True

    def test_user_support_includes_itself(self):
        support = AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)
        assert support.includes(AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)) is True

    def test_compliance_includes_itself(self):
        compliance = AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)
        assert compliance.includes(AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)) is True

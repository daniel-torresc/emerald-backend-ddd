from emerald.iam.domain.models.value_objects.system_role import SystemRole


class TestSystemRole:
    def test_has_exactly_three_values(self):
        assert len(SystemRole) == 3

    def test_user_value(self):
        assert SystemRole.USER.value == "USER"

    def test_admin_value(self):
        assert SystemRole.ADMIN.value == "ADMIN"

    def test_superadmin_value(self):
        assert SystemRole.SUPERADMIN.value == "SUPERADMIN"


# -- level property ------------------------------------------------------------


class TestSystemRoleLevel:
    def test_user_level_is_1(self):
        assert SystemRole.USER.level == 1

    def test_admin_level_is_2(self):
        assert SystemRole.ADMIN.level == 2

    def test_superadmin_level_is_3(self):
        assert SystemRole.SUPERADMIN.level == 3


# -- has_at_least() ------------------------------------------------------------


class TestSystemRoleHasAtLeast:
    # USER checks
    def test_user_has_at_least_user(self):
        assert SystemRole.USER.has_at_least(SystemRole.USER) is True

    def test_user_has_at_least_admin(self):
        assert SystemRole.USER.has_at_least(SystemRole.ADMIN) is False

    def test_user_has_at_least_superadmin(self):
        assert SystemRole.USER.has_at_least(SystemRole.SUPERADMIN) is False

    # ADMIN checks
    def test_admin_has_at_least_user(self):
        assert SystemRole.ADMIN.has_at_least(SystemRole.USER) is True

    def test_admin_has_at_least_admin(self):
        assert SystemRole.ADMIN.has_at_least(SystemRole.ADMIN) is True

    def test_admin_has_at_least_superadmin(self):
        assert SystemRole.ADMIN.has_at_least(SystemRole.SUPERADMIN) is False

    # SUPERADMIN checks
    def test_superadmin_has_at_least_user(self):
        assert SystemRole.SUPERADMIN.has_at_least(SystemRole.USER) is True

    def test_superadmin_has_at_least_admin(self):
        assert SystemRole.SUPERADMIN.has_at_least(SystemRole.ADMIN) is True

    def test_superadmin_has_at_least_superadmin(self):
        assert SystemRole.SUPERADMIN.has_at_least(SystemRole.SUPERADMIN) is True


# -- is_admin_or_above() ------------------------------------------------------


class TestSystemRoleIsAdminOrAbove:
    def test_user_is_not_admin_or_above(self):
        assert SystemRole.USER.is_admin_or_above() is False

    def test_admin_is_admin_or_above(self):
        assert SystemRole.ADMIN.is_admin_or_above() is True

    def test_superadmin_is_admin_or_above(self):
        assert SystemRole.SUPERADMIN.is_admin_or_above() is True


# -- can_access_admin_portal() -------------------------------------------------


class TestSystemRoleCanAccessAdminPortal:
    def test_user_cannot_access_admin_portal(self):
        assert SystemRole.USER.can_access_admin_portal() is False

    def test_admin_can_access_admin_portal(self):
        assert SystemRole.ADMIN.can_access_admin_portal() is True

    def test_superadmin_can_access_admin_portal(self):
        assert SystemRole.SUPERADMIN.can_access_admin_portal() is True

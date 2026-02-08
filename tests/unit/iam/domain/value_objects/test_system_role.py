from emerald.iam.domain.models.system_role import SystemRole


class TestSystemRole:
    def test_has_exactly_three_values(self):
        assert len(SystemRole) == 3

    def test_user_value(self):
        assert SystemRole.USER.value == "USER"

    def test_admin_value(self):
        assert SystemRole.ADMIN.value == "ADMIN"

    def test_superadmin_value(self):
        assert SystemRole.SUPERADMIN.value == "SUPERADMIN"

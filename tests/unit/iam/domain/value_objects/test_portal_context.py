from datetime import timedelta

from emerald.iam.domain.models.value_objects.portal_context import PortalContext


class TestPortalContext:
    def test_has_exactly_two_values(self):
        assert len(PortalContext) == 2

    def test_regular_value(self):
        assert PortalContext.REGULAR.value == "REGULAR"

    def test_admin_value(self):
        assert PortalContext.ADMIN.value == "ADMIN"

    def test_regular_refresh_ttl_is_seven_days(self):
        assert PortalContext.REGULAR.refresh_ttl == timedelta(days=7)

    def test_admin_refresh_ttl_is_four_hours(self):
        assert PortalContext.ADMIN.refresh_ttl == timedelta(hours=4)

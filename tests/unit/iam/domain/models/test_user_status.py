from emerald.iam.domain.models import UserStatus


class TestUserStatus:
    def test_has_four_values(self):
        assert len(UserStatus) == 4

    def test_pending_verification(self):
        assert UserStatus.PENDING_VERIFICATION.value == "PENDING_VERIFICATION"

    def test_active(self):
        assert UserStatus.ACTIVE.value == "ACTIVE"

    def test_suspended(self):
        assert UserStatus.SUSPENDED.value == "SUSPENDED"

    def test_deleted(self):
        assert UserStatus.DELETED.value == "DELETED"

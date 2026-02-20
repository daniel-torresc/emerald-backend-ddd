from datetime import timedelta

from emerald.iam.domain.constants import (
    ACCESS_TOKEN_TTL,
    MAX_CONCURRENT_SESSIONS,
    PASSWORD_MIN_LENGTH,
    PASSWORD_RESET_TOKEN_TTL,
    REFRESH_TOKEN_TTL_ADMIN,
    REFRESH_TOKEN_TTL_REGULAR,
)


class TestDomainConstants:
    def test_access_token_ttl_is_900_seconds(self):
        assert ACCESS_TOKEN_TTL == 900

    def test_refresh_token_ttl_regular_is_seven_days(self):
        assert REFRESH_TOKEN_TTL_REGULAR == timedelta(days=7)

    def test_refresh_token_ttl_admin_is_four_hours(self):
        assert REFRESH_TOKEN_TTL_ADMIN == timedelta(hours=4)

    def test_password_reset_token_ttl_is_one_hour(self):
        assert PASSWORD_RESET_TOKEN_TTL == timedelta(hours=1)

    def test_max_concurrent_sessions_is_five(self):
        assert MAX_CONCURRENT_SESSIONS == 5

    def test_password_min_length_is_twelve(self):
        assert PASSWORD_MIN_LENGTH == 12

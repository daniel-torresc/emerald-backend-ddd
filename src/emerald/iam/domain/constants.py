from datetime import timedelta

ACCESS_TOKEN_TTL: int = 900  # 15 minutes in seconds
REFRESH_TOKEN_TTL_REGULAR: timedelta = timedelta(days=7)
REFRESH_TOKEN_TTL_ADMIN: timedelta = timedelta(hours=4)
PASSWORD_RESET_TOKEN_TTL: timedelta = timedelta(hours=1)
REFRESH_TOKEN_TTL_SUPERADMIN: timedelta = timedelta(minutes=15)
MAX_CONCURRENT_SESSIONS: int = 5
MAX_PASSWORD_HISTORY: int = 5
PASSWORD_MIN_LENGTH: int = 12

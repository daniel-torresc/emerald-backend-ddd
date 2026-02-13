"""Domain constants for the Core Finance bounded context."""

MAX_SHARES_PER_ACCOUNT: int = 20

# Transaction string field limits
MAX_ORIGINAL_DESCRIPTION_LENGTH: int = 500
MAX_USER_DESCRIPTION_LENGTH: int = 500
MAX_MERCHANT_LENGTH: int = 200
MAX_COMMENTS_LENGTH: int = 1000

# Pagination defaults
DEFAULT_TRANSACTION_PAGE_SIZE: int = 50

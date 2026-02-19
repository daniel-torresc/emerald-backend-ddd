from decimal import Decimal

# Bank connection limits
MIN_SYNC_FREQUENCY_HOURS = 1
MAX_SYNC_FREQUENCY_HOURS = 24
DEFAULT_SYNC_FREQUENCY_HOURS = 6

# Failure thresholds
MAX_CONSECUTIVE_FAILURES = 3

# Retry backoff
RETRY_BASE_MINUTES = 15  # 15min, 30min, 60min
RETRY_MAX_MINUTES = 60

# Provider name limits
MAX_PROVIDER_NAME_LENGTH = 50

# Normalized transaction limits
MAX_DESCRIPTION_LENGTH = 500
# Aligned with core_finance MAX_MERCHANT_LENGTH by convention (not by import).
MAX_MERCHANT_LENGTH = 200

# Deduplication
AMOUNT_TOLERANCE = Decimal("0.01")  # ±0.01 for fuzzy matching

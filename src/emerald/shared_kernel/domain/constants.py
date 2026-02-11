from datetime import timedelta

from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)

# --- Default Retention Periods (spec 6.1) ---
DEFAULT_RETENTION: dict[DeletableEntityType, RetentionPeriod] = {
    DeletableEntityType.USER: RetentionPeriod(duration=30, unit=RetentionUnit.DAYS),
    DeletableEntityType.FINANCIAL_ACCOUNT: RetentionPeriod(duration=7, unit=RetentionUnit.YEARS),
    DeletableEntityType.TRANSACTION: RetentionPeriod(duration=7, unit=RetentionUnit.YEARS),
    DeletableEntityType.CARD: RetentionPeriod(duration=90, unit=RetentionUnit.DAYS),
    DeletableEntityType.ACCOUNT_SHARE: RetentionPeriod(duration=30, unit=RetentionUnit.DAYS),
    DeletableEntityType.TAXONOMY: RetentionPeriod(duration=7, unit=RetentionUnit.DAYS),
    DeletableEntityType.TAXONOMY_TERM: RetentionPeriod(duration=7, unit=RetentionUnit.DAYS),
    DeletableEntityType.BANK_CONNECTION: RetentionPeriod(duration=7, unit=RetentionUnit.DAYS),
}

# --- Regulatory Minimums (spec 6.2) ---
REGULATORY_MINIMUMS: dict[DeletableEntityType, RetentionPeriod] = {
    DeletableEntityType.FINANCIAL_ACCOUNT: RetentionPeriod(duration=7, unit=RetentionUnit.YEARS),
    DeletableEntityType.TRANSACTION: RetentionPeriod(duration=7, unit=RetentionUnit.YEARS),
}

# --- Cooling-Off Periods (spec 6.3) ---
COOLING_OFF_PERIODS: dict[DeletableEntityType, RetentionPeriod] = {
    DeletableEntityType.USER: RetentionPeriod(duration=1, unit=RetentionUnit.DAYS),
    DeletableEntityType.FINANCIAL_ACCOUNT: RetentionPeriod(duration=1, unit=RetentionUnit.DAYS),
}

# --- Retention Warning Schedule (spec 6.4) ---
RETENTION_WARNINGS: list[timedelta] = [
    timedelta(days=7),
    timedelta(hours=24),
]

# --- Soft Delete Cascade Rules (spec 7.1) ---
SOFT_DELETE_CASCADE_RULES: dict[DeletableEntityType, list[DeletableEntityType]] = {
    DeletableEntityType.USER: [
        DeletableEntityType.FINANCIAL_ACCOUNT,
        DeletableEntityType.TAXONOMY,
    ],
    DeletableEntityType.FINANCIAL_ACCOUNT: [
        DeletableEntityType.TRANSACTION,
        DeletableEntityType.CARD,
        DeletableEntityType.ACCOUNT_SHARE,
    ],
    DeletableEntityType.TAXONOMY: [
        DeletableEntityType.TAXONOMY_TERM,
    ],
    DeletableEntityType.TRANSACTION: [],
}

# --- Hard Delete Cascade Rules (spec 7.2) ---
HARD_DELETE_CASCADE_RULES: dict[DeletableEntityType, list[DeletableEntityType]] = {
    DeletableEntityType.USER: [
        DeletableEntityType.FINANCIAL_ACCOUNT,
        DeletableEntityType.TAXONOMY,
    ],
    DeletableEntityType.FINANCIAL_ACCOUNT: [
        DeletableEntityType.TRANSACTION,
        DeletableEntityType.CARD,
        DeletableEntityType.ACCOUNT_SHARE,
    ],
    DeletableEntityType.TAXONOMY: [
        DeletableEntityType.TAXONOMY_TERM,
    ],
    DeletableEntityType.TRANSACTION: [],
}

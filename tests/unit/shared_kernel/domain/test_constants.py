from datetime import timedelta

from emerald.shared_kernel.domain.constants import (
    COOLING_OFF_PERIODS,
    DEFAULT_RETENTION,
    HARD_DELETE_CASCADE_RULES,
    REGULATORY_MINIMUMS,
    RETENTION_WARNINGS,
    SOFT_DELETE_CASCADE_RULES,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


class TestDefaultRetention:
    def test_all_entity_types_present(self) -> None:
        for entity_type in DeletableEntityType:
            assert entity_type in DEFAULT_RETENTION, (
                f"{entity_type.value} missing from DEFAULT_RETENTION"
            )

    def test_exactly_eight_entries(self) -> None:
        assert len(DEFAULT_RETENTION) == 8


class TestRegulatoryMinimums:
    def test_exactly_two_entries(self) -> None:
        assert len(REGULATORY_MINIMUMS) == 2

    def test_contains_financial_account(self) -> None:
        assert DeletableEntityType.FINANCIAL_ACCOUNT in REGULATORY_MINIMUMS

    def test_contains_transaction(self) -> None:
        assert DeletableEntityType.TRANSACTION in REGULATORY_MINIMUMS

    def test_financial_account_is_seven_years(self) -> None:
        expected = RetentionPeriod(duration=7, unit=RetentionUnit.YEARS)
        assert REGULATORY_MINIMUMS[DeletableEntityType.FINANCIAL_ACCOUNT] == expected

    def test_transaction_is_seven_years(self) -> None:
        expected = RetentionPeriod(duration=7, unit=RetentionUnit.YEARS)
        assert REGULATORY_MINIMUMS[DeletableEntityType.TRANSACTION] == expected


class TestCoolingOffPeriods:
    def test_exactly_two_entries(self) -> None:
        assert len(COOLING_OFF_PERIODS) == 2

    def test_contains_user(self) -> None:
        assert DeletableEntityType.USER in COOLING_OFF_PERIODS

    def test_contains_financial_account(self) -> None:
        assert DeletableEntityType.FINANCIAL_ACCOUNT in COOLING_OFF_PERIODS

    def test_user_is_one_day(self) -> None:
        period = COOLING_OFF_PERIODS[DeletableEntityType.USER]
        assert period == RetentionPeriod(duration=1, unit=RetentionUnit.DAYS)

    def test_financial_account_is_one_day(self) -> None:
        period = COOLING_OFF_PERIODS[DeletableEntityType.FINANCIAL_ACCOUNT]
        assert period == RetentionPeriod(duration=1, unit=RetentionUnit.DAYS)


class TestRetentionWarnings:
    def test_two_entries(self) -> None:
        assert len(RETENTION_WARNINGS) == 2

    def test_first_warning_seven_days(self) -> None:
        assert RETENTION_WARNINGS[0] == timedelta(days=7)

    def test_second_warning_twenty_four_hours(self) -> None:
        assert RETENTION_WARNINGS[1] == timedelta(hours=24)


class TestSoftDeleteCascadeRules:
    def test_user_cascades_to_financial_account_and_taxonomy(self) -> None:
        children = SOFT_DELETE_CASCADE_RULES[DeletableEntityType.USER]
        assert DeletableEntityType.FINANCIAL_ACCOUNT in children
        assert DeletableEntityType.TAXONOMY in children

    def test_financial_account_cascades_to_transaction_card_share(self) -> None:
        children = SOFT_DELETE_CASCADE_RULES[DeletableEntityType.FINANCIAL_ACCOUNT]
        assert DeletableEntityType.TRANSACTION in children
        assert DeletableEntityType.CARD in children
        assert DeletableEntityType.ACCOUNT_SHARE in children

    def test_taxonomy_cascades_to_taxonomy_term(self) -> None:
        children = SOFT_DELETE_CASCADE_RULES[DeletableEntityType.TAXONOMY]
        assert DeletableEntityType.TAXONOMY_TERM in children

    def test_transaction_has_no_children(self) -> None:
        assert SOFT_DELETE_CASCADE_RULES[DeletableEntityType.TRANSACTION] == []

    def test_user_cascade_chain(self) -> None:
        """USER -> FINANCIAL_ACCOUNT -> TRANSACTION chain is resolvable."""
        user_children = SOFT_DELETE_CASCADE_RULES[DeletableEntityType.USER]
        assert DeletableEntityType.FINANCIAL_ACCOUNT in user_children

        account_children = SOFT_DELETE_CASCADE_RULES[DeletableEntityType.FINANCIAL_ACCOUNT]
        assert DeletableEntityType.TRANSACTION in account_children


class TestHardDeleteCascadeRules:
    def test_matches_soft_delete_structure(self) -> None:
        assert set(HARD_DELETE_CASCADE_RULES.keys()) == set(SOFT_DELETE_CASCADE_RULES.keys())
        for entity_type in HARD_DELETE_CASCADE_RULES:
            assert set(HARD_DELETE_CASCADE_RULES[entity_type]) == set(
                SOFT_DELETE_CASCADE_RULES[entity_type]
            ), f"Mismatch for {entity_type.value}"

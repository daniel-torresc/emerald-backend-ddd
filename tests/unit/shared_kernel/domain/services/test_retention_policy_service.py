import uuid
from datetime import UTC, datetime

import pytest

from emerald.shared_kernel.domain.exceptions.lifecycle_exceptions import BelowPlatformDefaultError
from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


class TestRetentionPolicyServiceEffectiveRetention:
    async def test_no_regulatory_no_user_pref_returns_platform_default(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        result = await service.get_effective_retention(DeletableEntityType.USER)

        # USER default is 30 days
        assert result == RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)

    async def test_regulatory_minimum_used_for_financial_account(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        result = await service.get_effective_retention(DeletableEntityType.FINANCIAL_ACCOUNT)

        # FINANCIAL_ACCOUNT: default=7 years, regulatory=7 years -> 7 years
        assert result == RetentionPeriod(duration=7, unit=RetentionUnit.YEARS)

    async def test_user_preference_higher_than_default_wins(self) -> None:
        repo = FakeRetentionPolicyRepository()
        user_id = uuid.uuid4()
        # USER default is 30 days; set user pref to 60 days
        await repo.save_user_preference(
            UserRetentionPreference(
                user_id=user_id,
                entity_type=DeletableEntityType.USER,
                retention_period=RetentionPeriod(60, RetentionUnit.DAYS),
            )
        )
        service = RetentionPolicyService(repo)

        result = await service.get_effective_retention(DeletableEntityType.USER, user_id)

        assert result == RetentionPeriod(duration=60, unit=RetentionUnit.DAYS)

    async def test_regulatory_wins_over_user_preference(self) -> None:
        repo = FakeRetentionPolicyRepository()
        user_id = uuid.uuid4()
        # FINANCIAL_ACCOUNT: regulatory=7 years; set user pref to 8 years
        # User pref is higher, so it should win
        await repo.save_user_preference(
            UserRetentionPreference(
                user_id=user_id,
                entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
                retention_period=RetentionPeriod(8, RetentionUnit.YEARS),
            )
        )
        service = RetentionPolicyService(repo)

        result = await service.get_effective_retention(
            DeletableEntityType.FINANCIAL_ACCOUNT, user_id
        )

        assert result == RetentionPeriod(duration=8, unit=RetentionUnit.YEARS)

    async def test_regulatory_wins_when_user_pref_is_lower(self) -> None:
        repo = FakeRetentionPolicyRepository()
        user_id = uuid.uuid4()
        # TRANSACTION: regulatory=7 years (2555 approx days)
        # Even if user pref is set to 7 years, regulatory matches
        await repo.save_user_preference(
            UserRetentionPreference(
                user_id=user_id,
                entity_type=DeletableEntityType.TRANSACTION,
                retention_period=RetentionPeriod(7, RetentionUnit.YEARS),
            )
        )
        service = RetentionPolicyService(repo)

        result = await service.get_effective_retention(DeletableEntityType.TRANSACTION, user_id)

        assert result == RetentionPeriod(duration=7, unit=RetentionUnit.YEARS)

    async def test_no_user_id_returns_max_of_regulatory_and_default(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        # CARD: no regulatory minimum, default is 90 days
        result = await service.get_effective_retention(DeletableEntityType.CARD)
        assert result == RetentionPeriod(duration=90, unit=RetentionUnit.DAYS)


class TestRetentionPolicyServiceHardDeleteDate:
    async def test_calculate_for_user(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)
        deleted_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

        result = await service.calculate_hard_delete_date(DeletableEntityType.USER, deleted_at)

        # USER default is 30 days
        expected = datetime(2025, 7, 1, 12, 0, 0, tzinfo=UTC)
        assert result == expected

    async def test_calculate_for_financial_account(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)
        deleted_at = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

        result = await service.calculate_hard_delete_date(
            DeletableEntityType.FINANCIAL_ACCOUNT, deleted_at
        )

        # FINANCIAL_ACCOUNT: 7 years
        expected = datetime(2032, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result == expected


class TestRetentionPolicyServiceSetUserPreference:
    async def test_valid_period_accepted_and_persisted(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)
        user_id = uuid.uuid4()
        period = RetentionPeriod(duration=60, unit=RetentionUnit.DAYS)

        await service.set_user_preference(DeletableEntityType.USER, user_id, period)

        stored = await repo.find_user_preference(DeletableEntityType.USER, user_id)
        assert stored is not None
        assert stored.retention_period == period
        assert stored.user_id == user_id
        assert stored.entity_type == DeletableEntityType.USER

    async def test_below_platform_default_raises(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)
        user_id = uuid.uuid4()

        # USER default is 30 days; setting 7 days should fail
        period = RetentionPeriod(duration=7, unit=RetentionUnit.DAYS)

        with pytest.raises(BelowPlatformDefaultError):
            await service.set_user_preference(DeletableEntityType.USER, user_id, period)


class TestRetentionPolicyServiceCoolingOff:
    def test_user_returns_one_day(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        result = service.get_cooling_off_period(DeletableEntityType.USER)

        assert result is not None
        assert result == RetentionPeriod(duration=1, unit=RetentionUnit.DAYS)

    def test_financial_account_returns_one_day(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        result = service.get_cooling_off_period(DeletableEntityType.FINANCIAL_ACCOUNT)

        assert result is not None
        assert result == RetentionPeriod(duration=1, unit=RetentionUnit.DAYS)

    def test_transaction_returns_none(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        result = service.get_cooling_off_period(DeletableEntityType.TRANSACTION)

        assert result is None

    def test_card_returns_none(self) -> None:
        repo = FakeRetentionPolicyRepository()
        service = RetentionPolicyService(repo)

        result = service.get_cooling_off_period(DeletableEntityType.CARD)

        assert result is None

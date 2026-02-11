import uuid

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


class TestUserRetentionPreferenceConstruction:
    def test_valid_construction_above_default(self) -> None:
        user_id = uuid.uuid4()
        pref = UserRetentionPreference(
            user_id=user_id,
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(60, RetentionUnit.DAYS),
        )
        assert pref.user_id == user_id
        assert pref.entity_type == DeletableEntityType.USER
        assert pref.retention_period == RetentionPeriod(60, RetentionUnit.DAYS)

    def test_valid_construction_equal_to_default(self) -> None:
        # USER default is 30 days
        pref = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(30, RetentionUnit.DAYS),
        )
        assert pref.retention_period == RetentionPeriod(30, RetentionUnit.DAYS)

    def test_below_default_raises(self) -> None:
        with pytest.raises(BelowPlatformDefaultError):
            UserRetentionPreference(
                user_id=uuid.uuid4(),
                entity_type=DeletableEntityType.USER,
                retention_period=RetentionPeriod(7, RetentionUnit.DAYS),
            )

    def test_construction_with_explicit_id(self) -> None:
        entity_id = uuid.uuid4()
        pref = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.CARD,
            retention_period=RetentionPeriod(90, RetentionUnit.DAYS),
            id=entity_id,
        )
        assert pref.id == entity_id

    def test_financial_account_equal_to_default(self) -> None:
        # FINANCIAL_ACCOUNT default is 7 years
        pref = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            retention_period=RetentionPeriod(7, RetentionUnit.YEARS),
        )
        assert pref.entity_type == DeletableEntityType.FINANCIAL_ACCOUNT

    def test_financial_account_below_default_raises(self) -> None:
        with pytest.raises(BelowPlatformDefaultError):
            UserRetentionPreference(
                user_id=uuid.uuid4(),
                entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
                retention_period=RetentionPeriod(1, RetentionUnit.YEARS),
            )


class TestUserRetentionPreferenceIdentity:
    def test_equality_by_id(self) -> None:
        entity_id = uuid.uuid4()
        a = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(60, RetentionUnit.DAYS),
            id=entity_id,
        )
        b = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(90, RetentionUnit.DAYS),
            id=entity_id,
        )
        assert a == b

    def test_different_ids_not_equal(self) -> None:
        a = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(60, RetentionUnit.DAYS),
        )
        b = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(60, RetentionUnit.DAYS),
        )
        assert a != b

    def test_hashable(self) -> None:
        pref = UserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            retention_period=RetentionPeriod(60, RetentionUnit.DAYS),
        )
        assert hash(pref) == hash(pref)

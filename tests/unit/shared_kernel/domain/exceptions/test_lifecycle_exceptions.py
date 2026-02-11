import uuid

import pytest

from emerald.shared_kernel.domain.exceptions import (
    DomainError,
    InvariantViolationError,
    ValidationError,
)
from emerald.shared_kernel.domain.exceptions.lifecycle_exceptions import (
    BelowPlatformDefaultError,
    BelowRegulatoryMinimumError,
    ConfirmationRequiredError,
    CoolingOffActiveError,
    HardDeleteNotScheduledError,
    ParentDeletedError,
)
from emerald.shared_kernel.domain.models.value_objects.cascade_summary import CascadeSummary
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class TestLifecycleExceptionHierarchy:
    @pytest.mark.parametrize(
        "exc_cls",
        [
            ParentDeletedError,
            ConfirmationRequiredError,
            CoolingOffActiveError,
            HardDeleteNotScheduledError,
            BelowRegulatoryMinimumError,
            BelowPlatformDefaultError,
        ],
    )
    def test_all_extend_invariant_violation(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, InvariantViolationError)

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ParentDeletedError,
            ConfirmationRequiredError,
            CoolingOffActiveError,
            HardDeleteNotScheduledError,
            BelowRegulatoryMinimumError,
            BelowPlatformDefaultError,
        ],
    )
    def test_all_extend_validation_error(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, ValidationError)

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ParentDeletedError,
            ConfirmationRequiredError,
            CoolingOffActiveError,
            HardDeleteNotScheduledError,
            BelowRegulatoryMinimumError,
            BelowPlatformDefaultError,
        ],
    )
    def test_all_extend_domain_error(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, DomainError)


class TestLifecycleExceptionCodes:
    @pytest.mark.parametrize(
        ("exc_cls", "expected_code"),
        [
            (ParentDeletedError, "PARENT_DELETED"),
            (CoolingOffActiveError, "COOLING_OFF_ACTIVE"),
            (HardDeleteNotScheduledError, "HARD_DELETE_NOT_SCHEDULED"),
            (BelowRegulatoryMinimumError, "BELOW_REGULATORY_MINIMUM"),
            (BelowPlatformDefaultError, "BELOW_PLATFORM_DEFAULT"),
        ],
    )
    def test_default_codes(
        self, exc_cls: type[InvariantViolationError], expected_code: str
    ) -> None:
        err = exc_cls("test")
        assert err.code == expected_code

    def test_confirmation_required_code(self) -> None:
        summary = CascadeSummary(
            target_entity_id=uuid.uuid4(),
            target_entity_type=DeletableEntityType.USER,
            affected_children=(),
            total_affected_count=1,
        )
        err = ConfirmationRequiredError(cascade_summary=summary)
        assert err.code == "CONFIRMATION_REQUIRED"


class TestLifecycleExceptionMessages:
    def test_parent_deleted_default_message(self) -> None:
        err = ParentDeletedError()
        assert "parent" in err.message.lower()

    def test_custom_message(self) -> None:
        err = ParentDeletedError("custom message")
        assert err.message == "custom message"

    def test_str_includes_message(self) -> None:
        err = CoolingOffActiveError()
        assert "cooling-off" in str(err).lower()


class TestConfirmationRequiredError:
    def test_cascade_summary_accessible(self) -> None:
        summary = CascadeSummary(
            target_entity_id=uuid.uuid4(),
            target_entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            affected_children=(),
            total_affected_count=1,
        )
        err = ConfirmationRequiredError(cascade_summary=summary)
        assert err.cascade_summary is summary
        assert err.cascade_summary.target_entity_type == DeletableEntityType.FINANCIAL_ACCOUNT

    def test_custom_message_with_summary(self) -> None:
        summary = CascadeSummary(
            target_entity_id=uuid.uuid4(),
            target_entity_type=DeletableEntityType.USER,
            affected_children=(),
            total_affected_count=1,
        )
        err = ConfirmationRequiredError(cascade_summary=summary, message="Please confirm deletion")
        assert err.message == "Please confirm deletion"
        assert err.cascade_summary is summary


class TestLifecycleExceptionCatchability:
    def test_parent_deleted_caught_by_invariant_violation(self) -> None:
        with pytest.raises(InvariantViolationError):
            raise ParentDeletedError()

    def test_below_platform_caught_by_domain_error(self) -> None:
        with pytest.raises(DomainError):
            raise BelowPlatformDefaultError()

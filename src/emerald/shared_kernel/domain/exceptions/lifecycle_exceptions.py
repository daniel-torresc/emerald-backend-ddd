from __future__ import annotations

from typing import TYPE_CHECKING

from emerald.shared_kernel.domain.exceptions.base import InvariantViolationError

if TYPE_CHECKING:
    from emerald.shared_kernel.domain.models.value_objects.cascade_summary import CascadeSummary


class ParentDeletedError(InvariantViolationError):
    """Raised when recovering a child whose parent is still deleted."""

    def __init__(self, message: str = "Cannot recover: parent entity is still deleted") -> None:
        super().__init__(message, code="PARENT_DELETED")


class ConfirmationRequiredError(InvariantViolationError):
    """Raised when hard delete is requested without confirmation."""

    def __init__(
        self,
        cascade_summary: CascadeSummary,
        message: str = "Hard delete requires explicit confirmation",
    ) -> None:
        self.cascade_summary = cascade_summary
        super().__init__(message, code="CONFIRMATION_REQUIRED")


class CoolingOffActiveError(InvariantViolationError):
    """Raised when attempting to execute hard delete during cooling-off."""

    def __init__(
        self, message: str = "Hard delete is in cooling-off period and cannot be executed yet"
    ) -> None:
        super().__init__(message, code="COOLING_OFF_ACTIVE")


class HardDeleteNotScheduledError(InvariantViolationError):
    """Raised when attempting to cancel when no hard delete is pending."""

    def __init__(self, message: str = "No hard delete is currently scheduled") -> None:
        super().__init__(message, code="HARD_DELETE_NOT_SCHEDULED")


class BelowRegulatoryMinimumError(InvariantViolationError):
    """Raised when attempting to set retention below regulatory minimum."""

    def __init__(
        self, message: str = "Retention period cannot be below regulatory minimum"
    ) -> None:
        super().__init__(message, code="BELOW_REGULATORY_MINIMUM")


class BelowPlatformDefaultError(InvariantViolationError):
    """Raised when user preference is below platform default."""

    def __init__(self, message: str = "Retention period cannot be below platform default") -> None:
        super().__init__(message, code="BELOW_PLATFORM_DEFAULT")

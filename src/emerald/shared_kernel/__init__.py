from emerald.shared_kernel.application.dtos.commands import Command
from emerald.shared_kernel.application.dtos.lifecycle_commands import (
    CancelHardDelete,
    ConfirmHardDelete,
    RecoverEntity,
    RequestHardDelete,
    SetUserRetentionPreference,
    SoftDeleteEntity,
)
from emerald.shared_kernel.application.ports.outbound.retention_policy_repository import (
    RetentionPolicyRepository,
)
from emerald.shared_kernel.application.ports.outbound.scheduled_deletion_port import (
    ScheduledDeletionPort,
)
from emerald.shared_kernel.application.ports.outbound.trash_query_port import TrashQueryPort
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork
from emerald.shared_kernel.domain.events import (
    DomainEvent,
    EntityHardDeleted,
    EntityRecovered,
    EntitySoftDeleted,
    HardDeleteCancelled,
    HardDeleteScheduled,
    HardDeleteTrigger,
    LifecycleEvent,
    RetentionWarningDue,
    RetentionWarningType,
)
from emerald.shared_kernel.domain.exceptions import (
    AlreadyDeletedError,
    AlreadyExistsError,
    AuthorizationError,
    BelowPlatformDefaultError,
    BelowRegulatoryMinimumError,
    ConfirmationRequiredError,
    ConflictError,
    CoolingOffActiveError,
    CurrencyMismatchError,
    DomainError,
    HardDeleteNotScheduledError,
    InvalidValueError,
    InvariantViolationError,
    NotDeletedError,
    NotFoundError,
    ParentDeletedError,
    ValidationError,
)
from emerald.shared_kernel.domain.models import (
    AggregateRoot,
    AuditableMixin,
    CascadeSummary,
    Currency,
    DateRange,
    DeletableEntityType,
    Entity,
    HardDeleteConfirmation,
    Money,
    PaginatedResult,
    RetentionPeriod,
    RetentionUnit,
    SoftDeletableMixin,
    TimestampedMixin,
    TrashItem,
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.services import RetentionPolicyService

__all__ = [
    # Application Layer
    "AbstractUnitOfWork",
    "Command",
    # Lifecycle Commands
    "CancelHardDelete",
    "ConfirmHardDelete",
    "RecoverEntity",
    "RequestHardDelete",
    "SetUserRetentionPreference",
    "SoftDeleteEntity",
    # Ports
    "RetentionPolicyRepository",
    "ScheduledDeletionPort",
    "TrashQueryPort",
    # Value Objects
    "CascadeSummary",
    "Currency",
    "DateRange",
    "DeletableEntityType",
    "HardDeleteConfirmation",
    "Money",
    "PaginatedResult",
    "RetentionPeriod",
    "RetentionUnit",
    "TrashItem",
    # Entities
    "Entity",
    "AggregateRoot",
    "UserRetentionPreference",
    # Mixins
    "AuditableMixin",
    "SoftDeletableMixin",
    "TimestampedMixin",
    # Domain Service
    "RetentionPolicyService",
    # Events
    "DomainEvent",
    "EntityHardDeleted",
    "EntityRecovered",
    "EntitySoftDeleted",
    "LifecycleEvent",
    "HardDeleteCancelled",
    "HardDeleteScheduled",
    "HardDeleteTrigger",
    "RetentionWarningDue",
    "RetentionWarningType",
    # Exceptions
    "AlreadyDeletedError",
    "AlreadyExistsError",
    "AuthorizationError",
    "BelowPlatformDefaultError",
    "BelowRegulatoryMinimumError",
    "ConflictError",
    "ConfirmationRequiredError",
    "CoolingOffActiveError",
    "CurrencyMismatchError",
    "DomainError",
    "HardDeleteNotScheduledError",
    "InvariantViolationError",
    "InvalidValueError",
    "NotDeletedError",
    "NotFoundError",
    "ParentDeletedError",
    "ValidationError",
]

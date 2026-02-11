# Spec 006: Data Lifecycle Management

**Version:** 1.0
**Status:** Implemented
**Bounded Context:** Shared Kernel (framework) + Cross-Cutting (orchestration)
**Dependencies:** 001 (Shared Kernel)
**Blocks:** 007 (Account Management), 013 (Classification & Taxonomies)

---

## 1. Overview

This spec defines the complete data lifecycle framework for all soft-deletable entities in the Emerald Finance Platform: soft delete orchestration, hard delete with safeguards, retention policies, trash management, recovery, and cascade behavior. It builds on the `SoftDeletableMixin` and `RetentionPeriod` from Spec 001 and adds the full lifecycle contracts, domain constants, and typed cascade registry.

**Key Principle:** Users have complete control over their data. Deleted items are recoverable from trash until a configurable retention period expires, at which point they are permanently removed. Hard delete is always an explicit, confirmed action with safeguards.

**Implementation Scope:** This spec implements the **framework and contracts only** — domain value objects, events, exceptions, commands, protocols, domain constants, and the `RetentionPolicyService` domain service. Concrete orchestration services (SoftDeleteService, HardDeleteService, RecoveryService, TrashQueryService) are deferred to when the entities they operate on are implemented (Specs 007, 009, 013, etc.).

---

## 2. Background & Context

### Problem Statement

The platform needs a consistent, auditable approach to data deletion that balances user convenience (accidental deletion recovery), regulatory compliance (retention minimums), and data sovereignty (user right to permanent deletion).

### Business Goals

- Users can recover accidentally deleted items from a trash view
- Regulatory retention minimums are enforced (cannot be shortened)
- Permanent deletion is available but requires explicit confirmation and safeguards
- Cascade behavior is predictable and well-documented
- Framework is extensible — new entity types plug in without changing core lifecycle logic

### Success Metrics

- All soft-deletable entities follow the same lifecycle state model
- Retention hierarchy (regulatory > platform > user) is enforced
- Cascade rules are centrally registered and type-safe
- Framework contracts enable bounded contexts to implement lifecycle operations independently

---

## 3. Scope

### In Scope (This Spec)

- `DeletableEntityType` enum — central registry of all deletable entity types
- Domain constants: retention defaults, cooling-off periods, regulatory minimums, retention warning schedule
- Typed cascade rule maps (soft delete and hard delete)
- Domain events (6 events)
- Commands (6 commands)
- Exceptions (6 new exceptions, 2 existing reused)
- Value objects: `TrashItem`, `CascadeSummary`, `HardDeleteConfirmation`
- `UserRetentionPreference` entity — stores per-user retention overrides
- Protocols (ports): `RetentionPolicyRepository`, `ScheduledDeletionPort`, `TrashQueryPort`
- `RetentionPolicyService` domain service — resolves retention hierarchy
- Fix `SoftDeletableMixin.__init__` signature from `**kwargs: object` to `**kwargs: Any`

### Out of Scope (Deferred)

- Concrete orchestration services (SoftDeleteService, HardDeleteService, RecoveryService) — implemented when entities exist (Specs 007+)
- TrashQueryService implementation — needs actual entities across contexts
- Scheduled cleanup job — infrastructure concern, implemented with concrete entities
- Entity-specific delete/recover methods — defined in each entity's spec
- Audit logging implementation — Spec 016 (this spec emits events that audit logging consumes)
- User-initiated hard delete confirmation UX — presentation layer
- Notification delivery — Spec 019 (this spec emits `RetentionWarningDue` events)

---

## 4. Entity Lifecycle States

All soft-deletable entities follow this state model:

```
┌──────────┐      soft_delete()     ┌──────────────┐     hard_delete()     ┌───────────────┐
│  ACTIVE  │───────────────────────►│ SOFT DELETED │──────────────────────►│ HARD DELETED  │
│          │                        │   (in Trash) │                       │  (Permanent)  │
└──────────┘                        └──────────────┘                       └───────────────┘
     ▲                                    │
     │              recover()             │
     └────────────────────────────────────┘
```

| State | Visibility | Recoverable | In Queries | In Calculations |
|-------|-----------|-------------|------------|-----------------|
| Active | Normal views | N/A | Yes | Yes |
| Soft Deleted | Trash view only | Yes | Only with `include_deleted=True` | No |
| Hard Deleted | Gone | No | No | No |

**Domain Rule:** Balance calculations and other domain aggregations **always** exclude soft-deleted entities, even when `include_deleted=True` is passed. The flag only affects visibility, not business calculations.

---

## 5. DeletableEntityType Enum

Central, type-safe registry of all entity types that support soft delete:

```python
class DeletableEntityType(Enum):
    USER = "USER"
    FINANCIAL_ACCOUNT = "FINANCIAL_ACCOUNT"
    TRANSACTION = "TRANSACTION"
    CARD = "CARD"
    ACCOUNT_SHARE = "ACCOUNT_SHARE"
    TAXONOMY = "TAXONOMY"
    TAXONOMY_TERM = "TAXONOMY_TERM"
    BANK_CONNECTION = "BANK_CONNECTION"
```

All lifecycle APIs use `DeletableEntityType` instead of raw strings.

---

## 6. Domain Constants

### 6.1 Default Retention Periods

| Entity Type | Default Retention | Rationale |
|-------------|-------------------|-----------|
| `USER` | 30 days | Allow recovery from accidental deletion |
| `FINANCIAL_ACCOUNT` | 7 years | Regulatory compliance (SOX, tax records) |
| `TRANSACTION` | 7 years | Regulatory compliance |
| `CARD` | 90 days | Lower recovery need |
| `ACCOUNT_SHARE` | 30 days | Access recovery window |
| `TAXONOMY` | 7 days | Lower importance |
| `TAXONOMY_TERM` | 7 days | Lower importance |
| `BANK_CONNECTION` | 7 days | Security consideration |

Defined as `DEFAULT_RETENTION: dict[DeletableEntityType, RetentionPeriod]`.

### 6.2 Regulatory Minimums

| Entity Type | Minimum Retention | Regulatory Reference |
|-------------|-------------------|----------------------|
| `FINANCIAL_ACCOUNT` | 7 years | Tax / SOX compliance |
| `TRANSACTION` | 7 years | Tax / SOX compliance |

All other entity types have no regulatory minimum (can be shortened to platform default).

Defined as `REGULATORY_MINIMUMS: dict[DeletableEntityType, RetentionPeriod]`.

### 6.3 Cooling-Off Periods

| Entity Type | Cooling-Off | Rationale |
|-------------|-------------|-----------|
| `USER` | 24 hours | High impact — cascades to everything |
| `FINANCIAL_ACCOUNT` | 24 hours | Contains financial history |
| All others | None | Lower risk |

Defined as `COOLING_OFF_PERIODS: dict[DeletableEntityType, RetentionPeriod]` (only entries for types with cooling-off).

### 6.4 Retention Warning Schedule

| Warning | Timing Before Hard Delete |
|---------|--------------------------|
| First warning | 7 days |
| Final warning | 24 hours |

Defined as `RETENTION_WARNINGS: list[timedelta]`.

---

## 7. Cascade Rules

### 7.1 Soft Delete Cascade Map

Typed data structure mapping parent entity type to list of child entity types affected by soft delete:

```python
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
    DeletableEntityType.TRANSACTION: [],  # Split children handled by Transaction spec
}
```

**Cascade Rules:**

- Children inherit the parent's `deleted_by` and `deletion_reason`
- Children get their own `hard_delete_scheduled_at` based on **their** entity type's retention
- Cascade is applied recursively (e.g., USER → FINANCIAL_ACCOUNT → TRANSACTION)
- Each cascaded child emits its own `EntitySoftDeleted` event

### 7.2 Hard Delete Cascade Map

Same structure, for hard delete. Hard delete cascade is **depth-first** (children deleted before parent):

```python
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
    DeletableEntityType.TRANSACTION: [],  # Split children handled by Transaction spec
}
```

**Hard Delete Cascade Rules:**

- Depth-first: children are permanently removed before parent
- Each cascaded entity gets its own `EntityHardDeleted` audit event
- Only entities already in trash (soft deleted) are affected — active entities are not touched

### 7.3 Recovery Rules

Recovery does **NOT** automatically recover children:

1. Validate entity is soft deleted
2. Validate parent is active (if entity has a parent) — raises `ParentDeletedError`
3. Clear deletion fields on the entity
4. Children remain in trash — user must recover them individually

**Exception — Split Transactions:**
- Recovering a split parent recovers all split children
- Recovering a split child also recovers the parent and all siblings
- This is handled by the Transaction spec (010), not this framework

---

## 8. Soft Delete Operation

When an entity is soft deleted (via application-layer orchestrator calling the mixin):

```
soft_delete_entity(entity, entity_type, deleted_by, reason?):
  1. Look up effective retention for entity_type (via RetentionPolicyService)
  2. Call entity.soft_delete(deleted_by, retention, reason)
     - Mixin validates entity is active (raises AlreadyDeletedError if not)
     - Mixin sets deleted_at, deleted_by, deletion_reason, hard_delete_scheduled_at
  3. Resolve cascade children from SOFT_DELETE_CASCADE_RULES
  4. Recursively soft delete each child (with their own retention period)
  5. Emit EntitySoftDeleted event for entity and each cascaded child
```

### Query Behavior

| Query Type | Default Behavior | With `include_deleted=True` |
|-----------|-----------------|---------------------------|
| List / Search | Excludes deleted | Includes deleted (with `deleted_at` visible) |
| Get by ID | Returns if active | Returns regardless of state |
| Aggregations | Excludes deleted | N/A — calculations **always** exclude deleted |

---

## 9. Hard Delete

### 9.1 Hard Delete Triggers

| Trigger | Description | Safeguards |
|---------|-------------|------------|
| User-Initiated | User explicitly requests permanent deletion from trash | Confirmation + cooling-off |
| Automatic | Retention period expires (`hard_delete_scheduled_at` reached) | Retention warning notifications |
| Admin-Initiated | Compliance or support action | Admin confirmation + audit |

### 9.2 User-Initiated Hard Delete Flow

```
1. request_hard_delete(entity_id, entity_type, requested_by) -> CascadeSummary
   - Validate entity is soft deleted (raises NotDeletedError if active)
   - Calculate cascade impact
   - Return CascadeSummary to caller

2. confirm_hard_delete(entity_id, entity_type, confirmed_by, confirmation) -> None
   - Validate HardDeleteConfirmation matches the CascadeSummary
   - If entity type has cooling-off period:
     a. Schedule hard delete for now + cooling_off_period
     b. Emit HardDeleteScheduled event
   - If no cooling-off:
     a. Execute hard delete immediately (see 9.4)

3. cancel_hard_delete(entity_id, entity_type, cancelled_by) -> None
   - Validate entity has a pending hard delete (cooling-off active)
   - Raises HardDeleteNotScheduledError if no pending hard delete
   - Cancel the scheduled hard delete
   - Revert to retention-based schedule
   - Emit HardDeleteCancelled event
```

### 9.3 Automatic Hard Delete (Retention Expiry)

```
Scheduled job runs periodically:
  1. Query entities where deleted_at IS NOT NULL and hard_delete_scheduled_at <= now
  2. For each entity:
     a. Execute hard delete cascade (depth-first)
     b. Emit EntityHardDeleted event per entity
```

### 9.4 Hard Delete Execution

```
execute_hard_delete(entity_id, entity_type):
  1. Resolve hard delete cascade children
  2. Depth-first: hard delete all children first
  3. Permanently remove the entity
  4. Emit EntityHardDeleted event for each removed entity
```

### 9.5 Hard Delete Safeguards

| Safeguard | Description | Applies To |
|-----------|-------------|------------|
| Must be in Trash | Only soft-deleted entities can be hard deleted | All triggers |
| Cascade Warning | Full CascadeSummary shown before confirmation | User-initiated |
| Confirmation Required | Explicit HardDeleteConfirmation acknowledgment | User-initiated |
| Cooling-Off Period | Delay before execution (see 6.3) | User-initiated (USER, FINANCIAL_ACCOUNT only) |
| Cancellable | Can cancel during cooling-off period | User-initiated with cooling-off |
| Final Audit Event | `EntityHardDeleted` event emitted before data removal | All triggers |
| Retention Warnings | `RetentionWarningDue` events at 7 days and 24 hours before auto hard delete | Automatic |

---

## 10. Retention Policies

### 10.1 Policy Hierarchy

Effective retention for an entity type is resolved as the **maximum** of all applicable levels:

```
effective_retention = max(
  1. Regulatory minimum   (immutable, cannot be reduced by anyone)
  2. Platform default      (domain constant, admin-changeable in future)
  3. User preference       (can only increase, never decrease below platform default)
)
```

**Rules:**

- Regulatory minimums are immutable and take precedence
- Platform defaults are domain constants (defined in 6.1), changeable by admin in future specs
- Users can extend retention (keep items longer) but cannot shorten below platform default
- If no user preference exists, platform default applies
- If no regulatory minimum exists, platform default is the floor

### 10.2 RetentionPolicyService (Domain Service)

```python
class RetentionPolicyService:
    """Resolves the effective retention period from the hierarchy."""

    def __init__(self, preference_repository: RetentionPolicyRepository) -> None: ...

    def get_effective_retention(
        self, entity_type: DeletableEntityType, user_id: UUID | None = None
    ) -> RetentionPeriod:
        """Resolve hierarchy: regulatory -> platform default -> user preference.
        Returns the longest applicable period."""

    def calculate_hard_delete_date(
        self, entity_type: DeletableEntityType, deleted_at: datetime, user_id: UUID | None = None
    ) -> datetime:
        """Returns deleted_at + get_effective_retention(entity_type, user_id)."""

    def set_user_preference(
        self, entity_type: DeletableEntityType, user_id: UUID, period: RetentionPeriod
    ) -> None:
        """Set user preference. Validates period >= platform default.
        Raises BelowPlatformDefaultError if too short."""

    def get_cooling_off_period(
        self, entity_type: DeletableEntityType
    ) -> RetentionPeriod | None:
        """Returns the cooling-off period for the entity type, or None if no cooling-off."""
```

---

## 11. Trash Management

### 11.1 TrashItem Value Object

```python
@dataclass(frozen=True)
class TrashItem:
    entity_id: UUID
    entity_type: DeletableEntityType
    display_name: str
    deleted_at: datetime
    deleted_by: UUID
    deletion_reason: str | None
    hard_delete_scheduled_at: datetime
    child_count: int  # Number of cascade children also in trash
```

`time_remaining` is a computed property: `hard_delete_scheduled_at - now`.

### 11.2 CascadeSummary Value Object

```python
@dataclass(frozen=True)
class CascadeSummary:
    target_entity_id: UUID
    target_entity_type: DeletableEntityType
    affected_children: tuple[TrashItem, ...]  # Immutable list
    total_affected_count: int  # Including the target itself
```

### 11.3 HardDeleteConfirmation Value Object

```python
@dataclass(frozen=True)
class HardDeleteConfirmation:
    entity_id: UUID
    entity_type: DeletableEntityType
    confirmed_by: UUID
    acknowledged_cascade_count: int  # Must match CascadeSummary.total_affected_count
    confirmed_at: datetime
```

### 11.4 TrashQueryPort (Protocol)

```python
class TrashQueryPort(Protocol):
    def list_trash(
        self,
        user_id: UUID,
        entity_type: DeletableEntityType | None = None,
        sort_by: str = "deleted_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult[TrashItem]: ...

    def get_cascade_summary(
        self, entity_id: UUID, entity_type: DeletableEntityType
    ) -> CascadeSummary: ...
```

### 11.5 Trash Access Rules

| User Role (Domain) | Can View in Trash | Can Recover | Can Hard Delete |
|--------------------|-------------------|-------------|-----------------|
| Owner | All deleted items for owned entities | Yes | Yes |
| Editor | Deleted transactions they created | No | No |
| Viewer | Nothing | No | No |

---

## 12. UserRetentionPreference Entity

Stores per-user retention overrides, managed by `RetentionPolicyService`:

```python
class UserRetentionPreference(Entity):
    """Per-user retention preference for a specific entity type."""

    user_id: UUID
    entity_type: DeletableEntityType
    retention_period: RetentionPeriod  # Must be >= platform default
```

- Extends `Entity` (not `AggregateRoot`) — managed by `RetentionPolicyService`
- One record per (user_id, entity_type) pair
- The `retention_period` must be >= the platform default for that entity type

---

## 13. Domain Events

All events are `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type = "data_lifecycle"`.

| Event | Trigger | Key Attributes |
|-------|---------|----------------|
| `EntitySoftDeleted` | Any entity soft deleted | `entity_type`, `entity_id`, `deleted_by`, `reason: str \| None`, `hard_delete_scheduled_at` |
| `EntityRecovered` | Any entity recovered from trash | `entity_type`, `entity_id`, `recovered_by` |
| `HardDeleteScheduled` | User confirms hard delete (cooling-off starts) | `entity_type`, `entity_id`, `scheduled_at`, `confirmed_by` |
| `HardDeleteCancelled` | User cancels during cooling-off | `entity_type`, `entity_id`, `cancelled_by` |
| `EntityHardDeleted` | Entity permanently removed | `entity_type`, `entity_id`, `trigger: HardDeleteTrigger` |
| `RetentionWarningDue` | Approaching automatic hard delete | `entity_type`, `entity_id`, `user_id`, `hard_delete_at`, `warning_type: RetentionWarningType` |

### Supporting Enums

```python
class HardDeleteTrigger(Enum):
    USER_INITIATED = "USER_INITIATED"
    AUTOMATIC = "AUTOMATIC"       # Retention expiry
    ADMIN_INITIATED = "ADMIN_INITIATED"

class RetentionWarningType(Enum):
    FIRST_WARNING = "FIRST_WARNING"   # 7 days before
    FINAL_WARNING = "FINAL_WARNING"   # 24 hours before
```

---

## 14. Commands

All commands are `@dataclass(frozen=True)` extending `Command`.

| Command | Key Attributes |
|---------|----------------|
| `SoftDeleteEntity` | `entity_id`, `entity_type`, `deleted_by`, `reason: str \| None` |
| `RecoverEntity` | `entity_id`, `entity_type`, `recovered_by` |
| `RequestHardDelete` | `entity_id`, `entity_type`, `requested_by` |
| `ConfirmHardDelete` | `entity_id`, `entity_type`, `confirmation: HardDeleteConfirmation` |
| `CancelHardDelete` | `entity_id`, `entity_type`, `cancelled_by` |
| `SetUserRetentionPreference` | `user_id`, `entity_type`, `retention_period` |

---

## 15. Exceptions

### New Exceptions (this spec)

| Exception | Code | Base Class | When Raised |
|-----------|------|------------|-------------|
| `ParentDeletedError` | `PARENT_DELETED` | `InvariantViolationError` | Recovering a child whose parent is still deleted |
| `ConfirmationRequiredError` | `CONFIRMATION_REQUIRED` | `InvariantViolationError` | Hard delete requested without confirmation |
| `CoolingOffActiveError` | `COOLING_OFF_ACTIVE` | `InvariantViolationError` | Attempting to execute hard delete during cooling-off |
| `HardDeleteNotScheduledError` | `HARD_DELETE_NOT_SCHEDULED` | `InvariantViolationError` | Attempting to cancel when no hard delete is pending |
| `BelowRegulatoryMinimumError` | `BELOW_REGULATORY_MINIMUM` | `InvariantViolationError` | Attempting to set retention below regulatory minimum |
| `BelowPlatformDefaultError` | `BELOW_PLATFORM_DEFAULT` | `InvariantViolationError` | User preference below platform default |

### Reused Exceptions (from Spec 001)

| Exception | When Reused |
|-----------|-------------|
| `AlreadyDeletedError` | Soft deleting an already-deleted entity |
| `NotDeletedError` | Recovering/hard deleting an active entity |

---

## 16. Repository Protocols (Ports)

### RetentionPolicyRepository

```python
class RetentionPolicyRepository(Protocol):
    def find_user_preference(
        self, entity_type: DeletableEntityType, user_id: UUID
    ) -> UserRetentionPreference | None: ...

    def save_user_preference(self, preference: UserRetentionPreference) -> None: ...

    def delete_user_preference(
        self, entity_type: DeletableEntityType, user_id: UUID
    ) -> None: ...
```

### ScheduledDeletionPort

```python
class ScheduledDeletionPort(Protocol):
    def find_due_for_hard_delete(
        self, as_of: datetime
    ) -> list[tuple[DeletableEntityType, UUID]]: ...

    def find_due_for_warning(
        self, warning_type: RetentionWarningType, as_of: datetime
    ) -> list[tuple[DeletableEntityType, UUID, UUID]]: ...
        # Returns (entity_type, entity_id, user_id)
```

---

## 17. SoftDeletableMixin Enhancement

Fix the `SoftDeletableMixin.__init__` signature to match project conventions:

```python
# Before (inconsistent):
def __init__(self, **kwargs: object) -> None:

# After (matches MRO forwarding convention):
def __init__(self, **kwargs: Any) -> None:
```

This aligns with the `**kwargs: Any` convention used by all other mixins for cooperative MRO.

---

## 18. Module Structure

All framework code lives in `src/emerald/shared_kernel/`, following the same ports-and-adapters structure used by IAM and other bounded contexts. Types are distributed by **role**, not grouped by feature:

```
src/emerald/shared_kernel/
├── domain/
│   ├── constants.py                             # NEW: retention defaults, cooling-off, cascade rules, warnings
│   ├── events/
│   │   ├── domain_event.py                      # Existing
│   │   └── lifecycle_events.py                  # NEW: 6 events + HardDeleteTrigger, RetentionWarningType
│   ├── exceptions/
│   │   ├── base.py                              # Existing (AlreadyDeletedError, NotDeletedError)
│   │   └── lifecycle_exceptions.py              # NEW: 6 exceptions
│   ├── models/
│   │   ├── base/
│   │   │   └── soft_deletable.py                # ENHANCED: **kwargs: Any
│   │   ├── entities/
│   │   │   └── user_retention_preference.py     # NEW
│   │   └── value_objects/
│   │       ├── retention_period.py              # Existing
│   │       ├── deletable_entity_type.py         # NEW: DeletableEntityType enum
│   │       ├── trash_item.py                    # NEW
│   │       ├── cascade_summary.py               # NEW
│   │       └── hard_delete_confirmation.py      # NEW
│   └── services/
│       └── retention_policy_service.py          # NEW: domain service
├── application/
│   ├── dtos/
│   │   ├── commands.py                          # Existing (Command base)
│   │   └── lifecycle_commands.py                # NEW: 6 commands
│   └── ports/
│       └── outbound/
│           ├── unit_of_work.py                  # Existing
│           ├── retention_policy_repository.py   # NEW
│           ├── scheduled_deletion_port.py       # NEW
│           └── trash_query_port.py              # NEW
└── __init__.py                                  # Updated: re-export lifecycle public API
```

---

## 19. Acceptance Criteria

### DeletableEntityType Enum

- [ ] Enum defines all 8 entity types: USER, FINANCIAL_ACCOUNT, TRANSACTION, CARD, ACCOUNT_SHARE, TAXONOMY, TAXONOMY_TERM, BANK_CONNECTION
- [ ] Used by all lifecycle value objects, events, commands, and constants

### Domain Constants

- [ ] `DEFAULT_RETENTION` maps each entity type to its default `RetentionPeriod`
- [ ] `REGULATORY_MINIMUMS` maps FINANCIAL_ACCOUNT and TRANSACTION to 7-year `RetentionPeriod`
- [ ] `COOLING_OFF_PERIODS` maps USER and FINANCIAL_ACCOUNT to 24-hour `RetentionPeriod`
- [ ] `RETENTION_WARNINGS` lists 7-day and 24-hour warning thresholds

### Cascade Rules

- [ ] `SOFT_DELETE_CASCADE_RULES` correctly maps parent -> children for all entity types
- [ ] `HARD_DELETE_CASCADE_RULES` matches soft delete cascade structure
- [ ] Cascade maps are type-safe (`dict[DeletableEntityType, list[DeletableEntityType]]`)
- [ ] Recursive cascade chains are resolvable (USER → FINANCIAL_ACCOUNT → TRANSACTION)

### Value Objects

- [ ] `TrashItem` is frozen dataclass with all specified attributes
- [ ] `CascadeSummary` is frozen dataclass with immutable `affected_children` tuple
- [ ] `HardDeleteConfirmation` is frozen dataclass with `acknowledged_cascade_count`
- [ ] All value objects use `DeletableEntityType` (not raw strings)

### Domain Events

- [ ] 6 events defined as frozen dataclasses extending `DomainEvent`
- [ ] `EntitySoftDeleted` includes `entity_type`, `entity_id`, `deleted_by`, `reason`, `hard_delete_scheduled_at`
- [ ] `EntityHardDeleted` includes `trigger: HardDeleteTrigger` enum
- [ ] `RetentionWarningDue` includes `warning_type: RetentionWarningType` enum

### Commands

- [ ] 6 commands defined as frozen dataclasses extending `Command`
- [ ] `ConfirmHardDelete` accepts `HardDeleteConfirmation` value object
- [ ] `SetUserRetentionPreference` accepts `DeletableEntityType` and `RetentionPeriod`

### Exceptions

- [ ] 6 new exceptions with unique codes, extending correct base classes
- [ ] `ConfirmationRequiredError` includes `cascade_summary: CascadeSummary` attribute
- [ ] All exceptions follow shared kernel hierarchy

### UserRetentionPreference Entity

- [ ] Extends `Entity` (not `AggregateRoot`)
- [ ] Has `user_id`, `entity_type`, `retention_period` attributes
- [ ] Validates `retention_period >= platform default` in constructor

### RetentionPolicyService

- [ ] `get_effective_retention()` returns max of regulatory minimum, platform default, and user preference
- [ ] `get_effective_retention()` without user_id returns max of regulatory minimum and platform default
- [ ] `calculate_hard_delete_date()` returns `deleted_at + effective_retention`
- [ ] `set_user_preference()` raises `BelowPlatformDefaultError` if period < platform default
- [ ] `set_user_preference()` persists via `RetentionPolicyRepository`
- [ ] `get_cooling_off_period()` returns correct period from constants or None

### Protocols (Ports)

- [ ] `RetentionPolicyRepository` uses `typing.Protocol` (structural subtyping)
- [ ] `ScheduledDeletionPort` uses `typing.Protocol`
- [ ] `TrashQueryPort` uses `typing.Protocol` with `list_trash()` and `get_cascade_summary()`

### SoftDeletableMixin Fix

- [ ] `__init__` signature changed from `**kwargs: object` to `**kwargs: Any`
- [ ] All existing tests still pass after the fix

### Quality Gates

- [ ] All tests pass (`uv run pytest`)
- [ ] No lint errors (`uv run ruff check .`)
- [ ] Code formatted (`uv run ruff format .`)
- [ ] Type check clean (`uv run ty check`)

---

## 20. Glossary

| Term | Definition |
|------|-----------|
| **Soft Delete** | Marking an entity as deleted without removing data; entity moves to trash |
| **Hard Delete** | Permanent, irreversible removal of entity data |
| **Retention Period** | Duration a soft-deleted entity remains in trash before auto hard delete |
| **Cooling-Off Period** | Delay between user confirming hard delete and actual execution |
| **Cascade** | Automatic propagation of delete/recover operations to child entities |
| **Regulatory Minimum** | Legally mandated minimum retention period that cannot be shortened |
| **Platform Default** | System-wide default retention period per entity type |
| **User Preference** | Per-user retention override (can only extend, not shorten) |

---

## 21. References

- [Spec 001: Shared Kernel](../spec-001-shared-kernel/) — `SoftDeletableMixin`, `RetentionPeriod`, base entity traits
- [Spec 007: Account Management](../spec-007-account-management/) — First consumer of lifecycle framework
- [Spec 013: Classification & Taxonomies](../spec-013-classification-and-taxonomies/) — Consumer of lifecycle framework
- [Spec 016: Audit Logging](../spec-016-audit-logging/) — Consumes `EntityHardDeleted` events
- [Spec 019: Notifications](../spec-019-notifications/) — Consumes `RetentionWarningDue` events

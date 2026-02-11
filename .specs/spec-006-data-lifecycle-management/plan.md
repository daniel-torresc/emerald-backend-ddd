# Data Lifecycle Management — Implementation Plan

**Spec:** `.specs/spec-006-data-lifecycle-management/spec.md`
**Version:** 1.0
**Date:** 2026-02-11

---

## 1. Overview

This plan implements the data lifecycle framework for the Emerald Finance Platform: a set of domain value objects, enums, domain constants, cascade rule maps, events, commands, exceptions, protocols (ports), one entity (`UserRetentionPreference`), and one domain service (`RetentionPolicyService`). Everything lives in the **Shared Kernel** bounded context since it provides framework contracts consumed by all other contexts.

**Key architectural decision:** This is a **framework-only** spec — no concrete orchestration services (SoftDeleteService, HardDeleteService, etc.) are implemented here. Those are deferred to the specs that introduce the entities they operate on (007, 009, 013, etc.). This spec delivers the contracts, constants, and the single domain service that resolves the retention hierarchy.

Additionally, this spec fixes the `SoftDeletableMixin.__init__` signature from `**kwargs: object` to `**kwargs: Any` to align with the cooperative MRO convention used by all other mixins.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| DeletableEntityType enum | Domain (Value Object) | `DeletableEntityType` |
| Retention defaults, cooling-off, cascade rules, warnings | Domain (Constants) | `constants.py` |
| HardDeleteTrigger, RetentionWarningType enums | Domain (Events) | Supporting enums in `lifecycle_events.py` |
| 6 lifecycle events | Domain (Events) | `lifecycle_events.py` |
| 6 lifecycle exceptions | Domain (Exceptions) | `lifecycle_exceptions.py` |
| TrashItem, CascadeSummary, HardDeleteConfirmation | Domain (Value Objects) | 3 new files |
| UserRetentionPreference | Domain (Entity) | `user_retention_preference.py` |
| RetentionPolicyService | Domain (Service) | `retention_policy_service.py` |
| SoftDeletableMixin fix | Domain (Base) | `soft_deletable.py` |
| 6 lifecycle commands | Application (DTOs) | `lifecycle_commands.py` |
| RetentionPolicyRepository | Application (Port) | `retention_policy_repository.py` |
| ScheduledDeletionPort | Application (Port) | `scheduled_deletion_port.py` |
| TrashQueryPort | Application (Port) | `trash_query_port.py` |

### 2.2 Component Diagram

```
src/emerald/shared_kernel/
├── domain/
│   ├── constants.py                              # NEW: all lifecycle constants
│   ├── events/
│   │   ├── __init__.py                           # UPDATED: re-export lifecycle events
│   │   ├── domain_event.py                       # Existing (unchanged)
│   │   └── lifecycle_events.py                   # NEW: 6 events + 2 supporting enums
│   ├── exceptions/
│   │   ├── __init__.py                           # UPDATED: re-export lifecycle exceptions
│   │   ├── base.py                               # Existing (unchanged)
│   │   └── lifecycle_exceptions.py               # NEW: 6 exceptions
│   ├── models/
│   │   ├── __init__.py                           # UPDATED: re-export new types
│   │   ├── base/
│   │   │   ├── __init__.py                       # Existing (unchanged)
│   │   │   └── soft_deletable.py                 # ENHANCED: **kwargs: Any
│   │   ├── entities/
│   │   │   ├── __init__.py                       # NEW
│   │   │   └── user_retention_preference.py      # NEW
│   │   └── value_objects/
│   │       ├── __init__.py                       # UPDATED: re-export new VOs
│   │       ├── deletable_entity_type.py          # NEW
│   │       ├── trash_item.py                     # NEW
│   │       ├── cascade_summary.py                # NEW
│   │       └── hard_delete_confirmation.py       # NEW
│   └── services/
│       ├── __init__.py                           # NEW
│       └── retention_policy_service.py           # NEW
├── application/
│   ├── dtos/
│   │   ├── __init__.py                           # UPDATED: re-export lifecycle commands
│   │   ├── commands.py                           # Existing (unchanged)
│   │   └── lifecycle_commands.py                 # NEW: 6 commands
│   └── ports/
│       └── outbound/
│           ├── __init__.py                       # UPDATED: re-export new ports
│           ├── unit_of_work.py                   # Existing (unchanged)
│           ├── retention_policy_repository.py    # NEW
│           ├── scheduled_deletion_port.py        # NEW
│           └── trash_query_port.py               # NEW
└── __init__.py                                   # UPDATED: re-export lifecycle public API
```

### 2.3 Ports and Adapters

| Port (Protocol) | Purpose | Location |
|------------------|---------|----------|
| `RetentionPolicyRepository` | CRUD for `UserRetentionPreference` | `application/ports/outbound/` |
| `ScheduledDeletionPort` | Query entities due for hard delete / warning | `application/ports/outbound/` |
| `TrashQueryPort` | List trash items and cascade summaries | `application/ports/outbound/` |

All ports use `typing.Protocol` (structural subtyping), matching project convention.

---

## 3. Technical Decisions

### 3.1 PaginatedResult Generic Type
**Decision:** Introduce a `PaginatedResult[T]` generic frozen dataclass in the shared kernel value objects for `TrashQueryPort.list_trash()` return type.
**Rationale:** The spec defines `list_trash() -> PaginatedResult[TrashItem]`. This is a generic reusable type needed by multiple contexts. Place it in `shared_kernel/domain/models/value_objects/paginated_result.py`.

### 3.2 Constants Location
**Decision:** Place all lifecycle constants in `shared_kernel/domain/constants.py`.
**Rationale:** Matches IAM pattern (`iam/domain/constants.py`). Cross-cutting lifecycle constants belong in the shared kernel since all bounded contexts reference them.

### 3.3 Cascade Rule Maps as Module-Level Constants
**Decision:** Define `SOFT_DELETE_CASCADE_RULES` and `HARD_DELETE_CASCADE_RULES` as module-level typed dicts in `constants.py`.
**Rationale:** These are static domain rules, not configuration. Typed `dict[DeletableEntityType, list[DeletableEntityType]]` provides compile-time safety.

### 3.4 RetentionPolicyService as Domain Service
**Decision:** `RetentionPolicyService` is a domain service (in `domain/services/`), not an application service.
**Rationale:** It encapsulates pure domain logic (retention hierarchy resolution). It takes a repository port as a dependency for user preference lookup, but the resolution logic itself is domain-level. This matches the spec's placement.

### 3.5 TrashItem.time_remaining as Computed Property
**Decision:** `time_remaining` is a `@property` on the frozen `TrashItem` dataclass that computes `hard_delete_scheduled_at - datetime.now(UTC)`.
**Rationale:** Spec says it's computed. Since `TrashItem` is a frozen dataclass, a property that computes on access (rather than storing) avoids stale data.

### 3.6 UserRetentionPreference Validation
**Decision:** `UserRetentionPreference.__init__` validates `retention_period >= DEFAULT_RETENTION[entity_type]` using the domain constants.
**Rationale:** The spec says "Validates `retention_period >= platform default` in constructor". The entity self-validates using the domain constants, consistent with the value object validation pattern.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Foundation (Value Objects, Enums)

#### TASK-001: Fix SoftDeletableMixin kwargs signature
**Layer:** Domain (Base)
**Depends On:** None

**Description:**
Change `SoftDeletableMixin.__init__` parameter from `**kwargs: object` to `**kwargs: Any` to align with the cooperative MRO convention used by `TimestampedMixin`, `AuditableMixin`, and `AggregateRoot`. Add the `from typing import Any` import.

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/base/soft_deletable.py` — change signature

**Acceptance Criteria:**
- [ ] `__init__(self, **kwargs: Any)` replaces `__init__(self, **kwargs: object)`
- [ ] `from typing import Any` added to imports
- [ ] All existing tests still pass

**Testing:**
- [ ] Run existing `tests/unit/shared_kernel/domain/base/test_soft_deletable.py` — must pass unchanged

---

#### TASK-002: Create DeletableEntityType enum
**Layer:** Domain (Value Object)
**Depends On:** None

**Description:**
Create the central enum registry of all deletable entity types. 8 members: USER, FINANCIAL_ACCOUNT, TRANSACTION, CARD, ACCOUNT_SHARE, TAXONOMY, TAXONOMY_TERM, BANK_CONNECTION.

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/value_objects/deletable_entity_type.py` — NEW

**Acceptance Criteria:**
- [ ] Enum with string values matching member names
- [ ] All 8 members defined per spec section 5

**Testing:**
- [ ] Unit tests: enum has exactly 8 members, values match names, iteration works

---

#### TASK-003: Create PaginatedResult generic type
**Layer:** Domain (Value Object)
**Depends On:** None

**Description:**
Create a generic `PaginatedResult[T]` frozen dataclass to support paginated query results. Attributes: `items: tuple[T, ...]`, `total: int`, `page: int`, `page_size: int`. Computed properties: `total_pages`, `has_next`, `has_previous`.

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/value_objects/paginated_result.py` — NEW

**Acceptance Criteria:**
- [ ] Generic frozen dataclass with type parameter `T`
- [ ] `items` as tuple (immutable), `total`, `page`, `page_size` attributes
- [ ] `total_pages`, `has_next`, `has_previous` computed properties
- [ ] Validation: `page >= 1`, `page_size >= 1`, `total >= 0`

**Testing:**
- [ ] Construction with valid data
- [ ] Computed property calculations (total_pages, has_next/previous)
- [ ] Validation errors for invalid page/page_size/total
- [ ] Generic type works with different item types

---

#### TASK-004: Create TrashItem value object
**Layer:** Domain (Value Object)
**Depends On:** TASK-002

**Description:**
Frozen dataclass with: `entity_id: UUID`, `entity_type: DeletableEntityType`, `display_name: str`, `deleted_at: datetime`, `deleted_by: UUID`, `deletion_reason: str | None`, `hard_delete_scheduled_at: datetime`, `child_count: int`. Computed `time_remaining` property.

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/value_objects/trash_item.py` — NEW

**Acceptance Criteria:**
- [ ] All specified attributes present
- [ ] `time_remaining` computed property returns `timedelta`
- [ ] Uses `DeletableEntityType` (not raw strings)
- [ ] Validation: `child_count >= 0`, `display_name` non-empty

**Testing:**
- [ ] Construction with all attributes
- [ ] `time_remaining` computation (positive and zero/negative cases)
- [ ] Validation of child_count and display_name

---

#### TASK-005: Create CascadeSummary value object
**Layer:** Domain (Value Object)
**Depends On:** TASK-002, TASK-004

**Description:**
Frozen dataclass with: `target_entity_id: UUID`, `target_entity_type: DeletableEntityType`, `affected_children: tuple[TrashItem, ...]`, `total_affected_count: int` (includes target itself).

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/value_objects/cascade_summary.py` — NEW

**Acceptance Criteria:**
- [ ] Immutable `affected_children` as tuple
- [ ] `total_affected_count` includes the target entity (>= 1)
- [ ] Uses `DeletableEntityType` and `TrashItem`

**Testing:**
- [ ] Construction with and without children
- [ ] Validation that `total_affected_count >= 1`
- [ ] Immutability of `affected_children`

---

#### TASK-006: Create HardDeleteConfirmation value object
**Layer:** Domain (Value Object)
**Depends On:** TASK-002

**Description:**
Frozen dataclass with: `entity_id: UUID`, `entity_type: DeletableEntityType`, `confirmed_by: UUID`, `acknowledged_cascade_count: int`, `confirmed_at: datetime`.

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/value_objects/hard_delete_confirmation.py` — NEW

**Acceptance Criteria:**
- [ ] All specified attributes present
- [ ] `acknowledged_cascade_count >= 1` validation
- [ ] Uses `DeletableEntityType`

**Testing:**
- [ ] Construction with valid data
- [ ] Validation of `acknowledged_cascade_count`

---

### Phase 2: Domain Layer — Constants & Rules

#### TASK-007: Create domain constants
**Layer:** Domain (Constants)
**Depends On:** TASK-002

**Description:**
Create `shared_kernel/domain/constants.py` with all lifecycle constants:
- `DEFAULT_RETENTION: dict[DeletableEntityType, RetentionPeriod]` — all 8 entity types
- `REGULATORY_MINIMUMS: dict[DeletableEntityType, RetentionPeriod]` — FINANCIAL_ACCOUNT, TRANSACTION (7 years)
- `COOLING_OFF_PERIODS: dict[DeletableEntityType, RetentionPeriod]` — USER, FINANCIAL_ACCOUNT (24 hours)
- `RETENTION_WARNINGS: list[timedelta]` — [7 days, 24 hours]
- `SOFT_DELETE_CASCADE_RULES: dict[DeletableEntityType, list[DeletableEntityType]]`
- `HARD_DELETE_CASCADE_RULES: dict[DeletableEntityType, list[DeletableEntityType]]`

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/constants.py` — NEW

**Acceptance Criteria:**
- [ ] All constants typed with `DeletableEntityType` keys (not raw strings)
- [ ] Default retention values match spec section 6.1
- [ ] Regulatory minimums match spec section 6.2
- [ ] Cooling-off periods match spec section 6.3
- [ ] Warning schedule: 7 days and 24 hours as `timedelta`
- [ ] Cascade rules match spec sections 7.1 and 7.2

**Testing:**
- [ ] Verify all 8 entity types present in `DEFAULT_RETENTION`
- [ ] Verify `REGULATORY_MINIMUMS` only has 2 entries
- [ ] Verify `COOLING_OFF_PERIODS` only has 2 entries
- [ ] Verify cascade rules are consistent (every type mentioned as child exists as key)
- [ ] Verify cascade chain resolution: USER → FINANCIAL_ACCOUNT → TRANSACTION

---

### Phase 3: Domain Layer — Events, Exceptions, Entity

#### TASK-008: Create lifecycle events and supporting enums
**Layer:** Domain (Events)
**Depends On:** TASK-002

**Description:**
Create 6 domain events as frozen dataclasses extending `DomainEvent` with `aggregate_type = "data_lifecycle"`. Also create 2 supporting enums: `HardDeleteTrigger` and `RetentionWarningType`.

Events:
1. `EntitySoftDeleted` — entity_type, entity_id, deleted_by, reason, hard_delete_scheduled_at
2. `EntityRecovered` — entity_type, entity_id, recovered_by
3. `HardDeleteScheduled` — entity_type, entity_id, scheduled_at, confirmed_by
4. `HardDeleteCancelled` — entity_type, entity_id, cancelled_by
5. `EntityHardDeleted` — entity_type, entity_id, trigger (HardDeleteTrigger)
6. `RetentionWarningDue` — entity_type, entity_id, user_id, hard_delete_at, warning_type (RetentionWarningType)

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/events/lifecycle_events.py` — NEW
- `src/emerald/shared_kernel/domain/events/__init__.py` — UPDATED: re-export

**Acceptance Criteria:**
- [ ] All 6 events are frozen dataclasses extending `DomainEvent`
- [ ] All events have `aggregate_type = "data_lifecycle"` as ClassVar
- [ ] `HardDeleteTrigger` has 3 members: USER_INITIATED, AUTOMATIC, ADMIN_INITIATED
- [ ] `RetentionWarningType` has 2 members: FIRST_WARNING, FINAL_WARNING
- [ ] Events use `DeletableEntityType` for entity_type fields

**Testing:**
- [ ] Each event can be instantiated with correct attributes
- [ ] `aggregate_type` class var is "data_lifecycle" for all events
- [ ] `event_id` and `occurred_at` auto-generated
- [ ] Enum members have correct values

---

#### TASK-009: Create lifecycle exceptions
**Layer:** Domain (Exceptions)
**Depends On:** None (uses existing base classes)

**Description:**
Create 6 new exceptions extending `InvariantViolationError`:
1. `ParentDeletedError` — code: `PARENT_DELETED`
2. `ConfirmationRequiredError` — code: `CONFIRMATION_REQUIRED`, includes `cascade_summary: CascadeSummary` attribute
3. `CoolingOffActiveError` — code: `COOLING_OFF_ACTIVE`
4. `HardDeleteNotScheduledError` — code: `HARD_DELETE_NOT_SCHEDULED`
5. `BelowRegulatoryMinimumError` — code: `BELOW_REGULATORY_MINIMUM`
6. `BelowPlatformDefaultError` — code: `BELOW_PLATFORM_DEFAULT`

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/exceptions/lifecycle_exceptions.py` — NEW
- `src/emerald/shared_kernel/domain/exceptions/__init__.py` — UPDATED: re-export

**Acceptance Criteria:**
- [ ] All 6 exceptions extend `InvariantViolationError`
- [ ] Each has unique code
- [ ] `ConfirmationRequiredError` has `cascade_summary` attribute
- [ ] Follow existing exception pattern (message + code in `__init__`)

**Testing:**
- [ ] Each exception instantiable with default and custom messages
- [ ] Correct codes on each exception
- [ ] `ConfirmationRequiredError.cascade_summary` accessible
- [ ] All inherit from `InvariantViolationError`

---

#### TASK-010: Create UserRetentionPreference entity
**Layer:** Domain (Entity)
**Depends On:** TASK-002, TASK-007

**Description:**
Create `UserRetentionPreference` extending `Entity` (not `AggregateRoot`). Attributes: `user_id: UUID`, `entity_type: DeletableEntityType`, `retention_period: RetentionPeriod`. Validates `retention_period >= DEFAULT_RETENTION[entity_type]` in constructor. Create the `models/entities/` directory with `__init__.py` for shared kernel.

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/models/entities/__init__.py` — NEW
- `src/emerald/shared_kernel/domain/models/entities/user_retention_preference.py` — NEW

**Acceptance Criteria:**
- [ ] Extends `Entity` (UUID identity, equality by ID)
- [ ] All 3 attributes accessible
- [ ] Constructor validates `retention_period >= DEFAULT_RETENTION[entity_type]`
- [ ] Raises `BelowPlatformDefaultError` if period is too short

**Testing:**
- [ ] Construction with valid data
- [ ] Validation rejects period below platform default
- [ ] Validation accepts period equal to platform default
- [ ] Validation accepts period above platform default
- [ ] Identity-based equality from `Entity`

---

### Phase 4: Domain Layer — Service

#### TASK-011: Create RetentionPolicyService
**Layer:** Domain (Service)
**Depends On:** TASK-002, TASK-007, TASK-009, TASK-010

**Description:**
Domain service with 4 methods:
- `get_effective_retention(entity_type, user_id=None)` — resolves max(regulatory, platform, user_preference)
- `calculate_hard_delete_date(entity_type, deleted_at, user_id=None)` — `deleted_at + effective_retention`
- `set_user_preference(entity_type, user_id, period)` — validates >= platform default, persists
- `get_cooling_off_period(entity_type)` — returns from constants or None

Depends on `RetentionPolicyRepository` protocol (created in Phase 5).

**Files to Create/Modify:**
- `src/emerald/shared_kernel/domain/services/__init__.py` — NEW
- `src/emerald/shared_kernel/domain/services/retention_policy_service.py` — NEW

**Acceptance Criteria:**
- [ ] `get_effective_retention()` returns max of all applicable levels
- [ ] Without user_id, returns max(regulatory, platform_default)
- [ ] With user_id, returns max(regulatory, platform_default, user_preference)
- [ ] `calculate_hard_delete_date()` returns `deleted_at + effective_retention`
- [ ] `set_user_preference()` raises `BelowPlatformDefaultError` if period < default
- [ ] `set_user_preference()` persists via repository
- [ ] `get_cooling_off_period()` returns period from `COOLING_OFF_PERIODS` or None

**Testing:**
- [ ] Effective retention: regulatory minimum wins over user preference when higher
- [ ] Effective retention: user preference wins when higher than default and regulatory
- [ ] Effective retention: platform default used when no regulatory and no user preference
- [ ] Hard delete date calculation with various entity types
- [ ] Set user preference: valid period accepted and persisted
- [ ] Set user preference: below platform default rejected
- [ ] Cooling-off: returns period for USER and FINANCIAL_ACCOUNT
- [ ] Cooling-off: returns None for entity types without cooling-off

---

### Phase 5: Application Layer — Commands & Ports

#### TASK-012: Create lifecycle commands
**Layer:** Application (DTOs)
**Depends On:** TASK-002, TASK-006

**Description:**
6 frozen dataclass commands extending `Command`:
1. `SoftDeleteEntity` — entity_id, entity_type, deleted_by, reason
2. `RecoverEntity` — entity_id, entity_type, recovered_by
3. `RequestHardDelete` — entity_id, entity_type, requested_by
4. `ConfirmHardDelete` — entity_id, entity_type, confirmation (HardDeleteConfirmation)
5. `CancelHardDelete` — entity_id, entity_type, cancelled_by
6. `SetUserRetentionPreference` — user_id, entity_type, retention_period

**Files to Create/Modify:**
- `src/emerald/shared_kernel/application/dtos/lifecycle_commands.py` — NEW
- `src/emerald/shared_kernel/application/dtos/__init__.py` — UPDATED: re-export

**Acceptance Criteria:**
- [ ] All 6 extend `Command` base
- [ ] All are frozen dataclasses
- [ ] Use `DeletableEntityType` and typed value objects (not raw strings)

**Testing:**
- [ ] Each command instantiable with correct attributes
- [ ] Frozen (immutable)

---

#### TASK-013: Create RetentionPolicyRepository protocol
**Layer:** Application (Port)
**Depends On:** TASK-002, TASK-010

**Description:**
Protocol with 3 methods:
- `find_user_preference(entity_type, user_id) -> UserRetentionPreference | None`
- `save_user_preference(preference: UserRetentionPreference) -> None`
- `delete_user_preference(entity_type, user_id) -> None`

**Files to Create/Modify:**
- `src/emerald/shared_kernel/application/ports/outbound/retention_policy_repository.py` — NEW

**Acceptance Criteria:**
- [ ] Uses `typing.Protocol` (structural subtyping)
- [ ] All 3 methods with correct signatures
- [ ] Correctly typed with `DeletableEntityType`, `UUID`, `UserRetentionPreference`

**Testing:**
- [ ] Protocol is runtime-checkable or structurally matchable
- [ ] Fake implementation in test fakes satisfies protocol

---

#### TASK-014: Create ScheduledDeletionPort protocol
**Layer:** Application (Port)
**Depends On:** TASK-002, TASK-008

**Description:**
Protocol with 2 methods:
- `find_due_for_hard_delete(as_of: datetime) -> list[tuple[DeletableEntityType, UUID]]`
- `find_due_for_warning(warning_type, as_of) -> list[tuple[DeletableEntityType, UUID, UUID]]`

**Files to Create/Modify:**
- `src/emerald/shared_kernel/application/ports/outbound/scheduled_deletion_port.py` — NEW

**Acceptance Criteria:**
- [ ] Uses `typing.Protocol`
- [ ] Both methods with correct signatures
- [ ] Uses `RetentionWarningType` from lifecycle events

**Testing:**
- [ ] Protocol structurally matchable

---

#### TASK-015: Create TrashQueryPort protocol
**Layer:** Application (Port)
**Depends On:** TASK-002, TASK-003, TASK-004, TASK-005

**Description:**
Protocol with 2 methods:
- `list_trash(user_id, entity_type?, sort_by?, sort_order?, page?, page_size?) -> PaginatedResult[TrashItem]`
- `get_cascade_summary(entity_id, entity_type) -> CascadeSummary`

**Files to Create/Modify:**
- `src/emerald/shared_kernel/application/ports/outbound/trash_query_port.py` — NEW

**Acceptance Criteria:**
- [ ] Uses `typing.Protocol`
- [ ] `list_trash` has all optional parameters with defaults
- [ ] Returns `PaginatedResult[TrashItem]`

**Testing:**
- [ ] Protocol structurally matchable

---

### Phase 6: Integration — Re-exports & Test Fakes

#### TASK-016: Update all __init__.py re-exports
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-015

**Description:**
Update all `__init__.py` files in the re-export chain to include new types:
1. `domain/models/value_objects/__init__.py` — add DeletableEntityType, TrashItem, CascadeSummary, HardDeleteConfirmation, PaginatedResult
2. `domain/models/__init__.py` — add new VOs + UserRetentionPreference + RetentionPolicyService
3. `domain/events/__init__.py` — add all lifecycle events + enums
4. `domain/exceptions/__init__.py` — add all lifecycle exceptions
5. `application/dtos/__init__.py` — add lifecycle commands
6. `application/ports/outbound/__init__.py` — add 3 new ports
7. `shared_kernel/__init__.py` — top-level re-export of all new public types

**Files to Modify:**
- `src/emerald/shared_kernel/domain/models/value_objects/__init__.py`
- `src/emerald/shared_kernel/domain/models/__init__.py`
- `src/emerald/shared_kernel/domain/events/__init__.py`
- `src/emerald/shared_kernel/domain/exceptions/__init__.py`
- `src/emerald/shared_kernel/application/dtos/__init__.py`
- `src/emerald/shared_kernel/application/ports/outbound/__init__.py`
- `src/emerald/shared_kernel/__init__.py`

**Acceptance Criteria:**
- [ ] All new public types accessible via `from emerald.shared_kernel import ...`
- [ ] Explicit `__all__` updated in every module
- [ ] Import chain: file → package `__init__` → domain/app `__init__` → context `__init__`

**Testing:**
- [ ] Import smoke tests: `from emerald.shared_kernel import DeletableEntityType, TrashItem, ...`

---

#### TASK-017: Create test fakes and complete test suite
**Layer:** Testing
**Depends On:** TASK-001 through TASK-016

**Description:**
Create test fakes for the new protocols and a comprehensive test suite:
1. `tests/unit/shared_kernel/fakes.py` — `FakeRetentionPolicyRepository` (in-memory dict)
2. Test files organized by domain layer:
   - `tests/unit/shared_kernel/domain/value_objects/test_deletable_entity_type.py`
   - `tests/unit/shared_kernel/domain/value_objects/test_paginated_result.py`
   - `tests/unit/shared_kernel/domain/value_objects/test_trash_item.py`
   - `tests/unit/shared_kernel/domain/value_objects/test_cascade_summary.py`
   - `tests/unit/shared_kernel/domain/value_objects/test_hard_delete_confirmation.py`
   - `tests/unit/shared_kernel/domain/events/test_lifecycle_events.py`
   - `tests/unit/shared_kernel/domain/exceptions/test_lifecycle_exceptions.py`
   - `tests/unit/shared_kernel/domain/entities/test_user_retention_preference.py`
   - `tests/unit/shared_kernel/domain/services/test_retention_policy_service.py`
   - `tests/unit/shared_kernel/domain/test_constants.py`
   - `tests/unit/shared_kernel/application/test_lifecycle_commands.py`

**Files to Create:**
- `tests/unit/shared_kernel/fakes.py` — NEW
- 11 test files as listed above — NEW
- `tests/unit/shared_kernel/domain/entities/__init__.py` — NEW
- `tests/unit/shared_kernel/domain/services/__init__.py` — NEW

**Acceptance Criteria:**
- [ ] `FakeRetentionPolicyRepository` implements all 3 protocol methods
- [ ] All value objects tested: construction, validation, computed properties
- [ ] All events tested: instantiation, aggregate_type, auto-generated fields
- [ ] All exceptions tested: codes, messages, inheritance, ConfirmationRequiredError.cascade_summary
- [ ] UserRetentionPreference tested: construction, validation, entity identity
- [ ] RetentionPolicyService tested: all 4 methods with all hierarchy combinations
- [ ] Constants tested: completeness, type safety, cascade chain consistency
- [ ] Commands tested: instantiation, immutability
- [ ] All tests use `dict[str, Any]` for factory defaults per project convention

**Testing:**
- [ ] All new tests pass
- [ ] All existing 929 tests still pass

---

### Phase 7: Quality Gates

#### TASK-018: Run quality gates
**Layer:** Cross-cutting
**Depends On:** TASK-017

**Description:**
Run all quality checks to ensure the implementation meets project standards:
1. `uv run pytest` — all tests pass
2. `uv run ruff check .` — no lint errors
3. `uv run ruff format .` — code formatted
4. `uv run ty check` — type check clean

**Acceptance Criteria:**
- [ ] All tests pass (929 existing + new lifecycle tests)
- [ ] Zero ruff check violations
- [ ] Zero ruff format changes
- [ ] Zero ty check errors

---

## 5. Task Dependency Graph

```
TASK-001 (SoftDeletableMixin fix) ─────────────────────────────────────────────┐
                                                                               │
TASK-002 (DeletableEntityType) ─┬──► TASK-004 (TrashItem) ──┬──► TASK-005 ──┐ │
                                │                            │  (Cascade)    │ │
                                ├──► TASK-006 (Confirmation) │               │ │
                                │                            │               │ │
                                ├──► TASK-007 (Constants) ───┼──► TASK-010 ──┤ │
                                │                            │  (Entity)     │ │
                                ├──► TASK-008 (Events) ──────┤               │ │
                                │                            │               │ │
                                └──► TASK-009 (Exceptions) ──┤               │ │
                                                             │               │ │
TASK-003 (PaginatedResult) ─────┘                            │               │ │
                                                             │               │ │
                                TASK-010 + TASK-007 ─────────┴──► TASK-011 ──┤ │
                                                                (Service)    │ │
                                TASK-002 + TASK-006 ──────────► TASK-012 ────┤ │
                                                               (Commands)    │ │
                                TASK-002 + TASK-010 ──────────► TASK-013 ────┤ │
                                                            (RetentionRepo)  │ │
                                TASK-002 + TASK-008 ──────────► TASK-014 ────┤ │
                                                         (ScheduledDelPort)  │ │
                                TASK-002..005 ────────────────► TASK-015 ────┤ │
                                                            (TrashQueryPort) │ │
                                                                             │ │
                                TASK-001..015 ────────────────► TASK-016 ────┤ │
                                                              (Re-exports)   │ │
                                                                             │ │
                                TASK-016 ─────────────────────► TASK-017 ────┘ │
                                                               (Tests)        │
                                                                              │
                                TASK-017 ─────────────────────► TASK-018 ─────┘
                                                             (Quality Gates)
```

**Parallelizable groups:**
- **Group A (parallel):** TASK-001, TASK-002, TASK-003
- **Group B (parallel, after TASK-002):** TASK-004, TASK-006, TASK-007, TASK-008, TASK-009
- **Group C (after Group B):** TASK-005 (needs TASK-004), TASK-010 (needs TASK-007, TASK-009)
- **Group D (parallel, after Group C):** TASK-011, TASK-012, TASK-013, TASK-014, TASK-015
- **Group E (sequential):** TASK-016 → TASK-017 → TASK-018

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `RetentionPeriod` comparison edge cases (months vs days) | Low | Medium | Existing `to_days()` approximation is already used; add tests for edge cases |
| `ty` strict type checking on generic `PaginatedResult[T]` | Medium | Low | Test with `ty check` early; may need explicit type annotations |
| Circular import between constants and value objects | Low | High | Constants imports VOs (DeletableEntityType, RetentionPeriod) — no reverse dep |
| Large `__init__.py` re-export surface | Low | Low | Follow existing pattern; alphabetical ordering |
| `ConfirmationRequiredError` holding `CascadeSummary` may complicate exception hierarchy | Low | Low | Store as attribute, not constructor param to base class |

---

## 7. Definition of Done

- [ ] All 18 tasks completed
- [ ] All acceptance criteria met
- [ ] `SoftDeletableMixin` fix applied and verified
- [ ] 4 new value objects + 1 generic type implemented
- [ ] 1 enum + 2 supporting enums implemented
- [ ] Domain constants with all lifecycle rules
- [ ] 6 domain events implemented
- [ ] 6 domain exceptions implemented
- [ ] 1 domain entity (UserRetentionPreference) implemented
- [ ] 1 domain service (RetentionPolicyService) implemented
- [ ] 6 commands implemented
- [ ] 3 protocol ports implemented
- [ ] All `__init__.py` re-exports updated
- [ ] Test fakes created for new protocols
- [ ] Comprehensive test suite passing
- [ ] All 929 existing tests still passing
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format .` — clean
- [ ] `uv run ty check` — clean

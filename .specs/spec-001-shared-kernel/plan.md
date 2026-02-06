# Shared Kernel Implementation Plan

**Spec:** `.specs/spec-001-shared-kernel/spec.md`
**Version:** 1.0
**Date:** 2026-02-05

---

## 1. Overview

Implement the foundational Shared Kernel for the Emerald Finance Platform — the innermost domain layer that all bounded contexts depend on. This includes four immutable value objects (Money, Currency, DateRange, RetentionPeriod), four composable entity traits (Identity, Timestamped, Soft-Deletable, Auditable), an AggregateRoot base type with event collection, a domain event base, and a structured exception hierarchy.

Since the Shared Kernel is **pure domain layer** with zero external dependencies, there are no application services, ports, adapters, or infrastructure components. Every type uses only the Python standard library.

This is also a **greenfield project** — we must bootstrap the project structure, `pyproject.toml`, and test infrastructure before building domain types.

---

## 2. Architecture Design

### 2.1 Layer Mapping

The Shared Kernel lives entirely in the **Domain Layer**. It has no application, infrastructure, or interface layer components.

| Requirement | Layer | Components |
|-------------|-------|------------|
| REQ-VO-001 (Money) | Domain | `Money` value object |
| REQ-VO-002 (Currency) | Domain | `Currency` enum |
| REQ-VO-003 (DateRange) | Domain | `DateRange` value object |
| REQ-VO-004 (RetentionPeriod) | Domain | `RetentionPeriod` value object, `RetentionUnit` enum |
| REQ-TRAIT-001 (Identity) | Domain | `Entity` base class |
| REQ-TRAIT-002 (Timestamped) | Domain | `TimestampedMixin` |
| REQ-TRAIT-003 (Soft-Deletable) | Domain | `SoftDeletableMixin` |
| REQ-TRAIT-004 (Auditable) | Domain | `AuditableMixin` |
| REQ-AGG-001 (AggregateRoot) | Domain | `AggregateRoot` base class |
| REQ-EVT-001 (DomainEvent) | Domain | `DomainEvent` base class |
| REQ-EXC-001 (Exceptions) | Domain | Exception hierarchy rooted at `DomainError` |

### 2.2 Project Structure

```
emerald-backend-ddd/
├── pyproject.toml                          # Project config, uv managed
├── src/
│   └── emerald/
│       ├── __init__.py
│       └── shared_kernel/                  # Spec 001
│           ├── __init__.py                 # Public API exports
│           ├── value_objects/
│           │   ├── __init__.py
│           │   ├── currency.py             # Currency enum
│           │   ├── money.py                # Money value object
│           │   ├── date_range.py           # DateRange value object
│           │   └── retention_period.py     # RetentionUnit enum + RetentionPeriod VO
│           ├── entities/
│           │   ├── __init__.py
│           │   ├── entity.py               # Entity base (Identity trait)
│           │   ├── timestamped.py          # TimestampedMixin
│           │   ├── soft_deletable.py       # SoftDeletableMixin
│           │   ├── auditable.py            # AuditableMixin
│           │   └── aggregate_root.py       # AggregateRoot base
│           ├── events/
│           │   ├── __init__.py
│           │   └── domain_event.py         # DomainEvent base class
│           └── exceptions/
│               ├── __init__.py
│               └── base.py                 # Full exception hierarchy
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── unit/
        ├── __init__.py
        └── shared_kernel/
            ├── __init__.py
            ├── value_objects/
            │   ├── __init__.py
            │   ├── test_currency.py
            │   ├── test_money.py
            │   ├── test_date_range.py
            │   └── test_retention_period.py
            ├── entities/
            │   ├── __init__.py
            │   ├── test_entity.py
            │   ├── test_timestamped.py
            │   ├── test_soft_deletable.py
            │   ├── test_auditable.py
            │   └── test_aggregate_root.py
            ├── events/
            │   ├── __init__.py
            │   └── test_domain_event.py
            └── exceptions/
                ├── __init__.py
                └── test_exceptions.py
```

### 2.3 Cross-Context Package Layout (Forward-Looking)

The Shared Kernel establishes the top-level package structure that future bounded contexts will follow:

```
src/emerald/
├── shared_kernel/          ← Spec 001 (this plan)
├── iam/                    ← Future: Specs 002-005
│   ├── domain/
│   ├── application/
│   └── adapters/
├── core_finance/           ← Future: Specs 007-012
│   ├── domain/
│   ├── application/
│   └── adapters/
├── classification/         ← Future: Specs 013-014
│   ├── domain/
│   ├── application/
│   └── adapters/
└── integrations/           ← Future: Spec 015
    ├── domain/
    ├── application/
    └── adapters/
```

The Shared Kernel is unique: it has no application/adapters layers because it contains only pure domain types. Future bounded contexts will have the full Clean Architecture layer structure.

### 2.4 Ports and Adapters

Not applicable — the Shared Kernel is pure domain layer with no external dependencies to abstract.

---

## 3. Technical Decisions

### 3.1 Value Object Immutability

**Decision:** Use `@dataclass(frozen=True)` for all value objects.
**Rationale:** Python's frozen dataclasses provide immutability, value equality, and hashability out of the box. This aligns with both the spec requirements and the architecture-patterns domain model guidance.
**Alternatives Considered:**
- `NamedTuple` — less flexible, no custom `__init__` validation
- Manual `__setattr__` override — more boilerplate, error-prone
- `attrs` with `frozen=True` — introduces third-party dependency

### 3.2 Currency as Enum

**Decision:** Implement `Currency` as a standard Python `Enum` with named members carrying attributes (code, symbol, name, decimal_places).
**Rationale:** The spec explicitly requires a static enum where adding currencies requires code changes. Python's `Enum` provides the exact semantics: immutable, hashable, singleton members.
**Alternatives Considered:**
- `@dataclass(frozen=True)` with class-level constants — doesn't prevent duplicate instances, no enum iteration
- Database-managed master data — explicitly rejected by spec (BR-CUR-002)

### 3.3 Entity Traits as Mixins

**Decision:** Implement entity traits as mixin classes that can be composed with multiple inheritance.
**Rationale:** The spec describes traits as "composable building blocks." Python's MRO (Method Resolution Order) handles multiple inheritance cleanly. AggregateRoot composes Identity + Timestamped; concrete aggregates can additionally compose SoftDeletable + Auditable as needed.
**Alternatives Considered:**
- Single deep inheritance chain — too rigid, forces all entities to have all traits
- Protocol-based structural typing — protocols define interfaces, not behavior; traits need default implementations
- Composition over inheritance (embedded helper objects) — adds indirection, complicates attribute access

### 3.4 Calendar-Accurate Date Arithmetic for RetentionPeriod

**Decision:** Use `python-dateutil` (`relativedelta`) for `RetentionPeriod.expiration_from()`.
**Rationale:** Calendar-accurate month/year arithmetic (e.g., "1 month from Jan 31 = Feb 28") requires handling variable month lengths and leap years. `relativedelta` is the standard, battle-tested solution. The spec allows this: "Calendar-accurate date arithmetic (e.g., `dateutil.relativedelta`) may be used — this is an implementation choice." While `dateutil` is technically a third-party library, it's a minimal, stable dependency that the spec explicitly permits, and it avoids reimplementing complex calendar math with potential edge-case bugs.
**Alternatives Considered:**
- Manual implementation — error-prone for edge cases (month-end boundaries, leap years), would duplicate `dateutil`'s battle-tested logic
- Python 3.13+ stdlib only — `datetime.timedelta` only supports days, not months/years

### 3.5 Timestamp Generation Strategy

**Decision:** Use `datetime.now(UTC)` for timestamp generation, injected via default factory.
**Rationale:** Entity constructors need timezone-aware UTC timestamps. Using `datetime.now(UTC)` directly in default values makes construction simple. For tests requiring deterministic timestamps, constructors accept explicit values.
**Alternatives Considered:**
- Clock interface injection — over-engineering for the domain layer; complicates every entity constructor
- `time.time()` + conversion — less readable, still not deterministic in tests

### 3.6 Testing Framework

**Decision:** Use `pytest` as the test framework.
**Rationale:** Industry standard for Python, excellent fixture support, parametric testing for edge cases, clean assertion syntax. No additional test framework dependencies (like `hypothesis`) for the initial implementation.
**Alternatives Considered:**
- `unittest` — more verbose, less Pythonic
- `hypothesis` — property-based testing is valuable but can be added later

### 3.7 Entity `__eq__` and `__hash__` via Base Class

**Decision:** Implement `__eq__` and `__hash__` in the `Entity` base class based on `id` field.
**Rationale:** BR-ID-003 requires identity-based equality. Implementing once in the base class avoids duplication across every entity subclass.
**Alternatives Considered:**
- Abstract method requiring each subclass to implement — adds boilerplate, risks inconsistency

---

## 4. Implementation Tasks

### Phase 1: Project Bootstrap

#### TASK-001: Initialize Project with uv

**Layer:** Infrastructure (project config)
**Depends On:** None

**Description:**
Create the project skeleton: `pyproject.toml` with `uv` as the package manager (venv with Python 3.13+), `src/` layout with namespace packages, and test infrastructure. Configure `ruff` for linting/formatting, `ty` for type checking, and `pytest` for testing.

**Files to Create:**
- `pyproject.toml` — Project metadata, dependencies (`python-dateutil`), dev dependencies (`pytest`, `ruff`), `[tool.ruff]` and `[tool.pytest]` config
- `src/emerald/__init__.py` — Top-level namespace package (empty)
- `src/emerald/shared_kernel/__init__.py` — Shared kernel package (will be populated in TASK-013)
- `tests/__init__.py` — Test root
- `tests/conftest.py` — Shared fixtures (empty initially)
- `tests/unit/__init__.py`
- `tests/unit/shared_kernel/__init__.py`

**Acceptance Criteria:**
- [ ] `uv sync` succeeds
- [ ] `uv run pytest` runs (0 tests collected, exits clean)
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `src/` layout with `emerald` namespace is importable

---

### Phase 2: Domain Layer — Exception Hierarchy

#### TASK-002: Implement Domain Exception Hierarchy

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Implement the complete exception hierarchy as specified in REQ-EXC-001. Every exception type extends `DomainError` and carries `code` (machine-readable) and `message` (human-readable) attributes. Each subtype has a sensible default `code` that can be overridden at construction.

**Files to Create:**
- `src/emerald/shared_kernel/exceptions/__init__.py` — Re-exports all exception types
- `src/emerald/shared_kernel/exceptions/base.py` — Full hierarchy:
  - `DomainError(Exception)` — base with `code` and `message`
  - `ValidationError(DomainError)`
  - `InvalidValueError(ValidationError)` — default code: `"INVALID_VALUE"`
  - `InvariantViolationError(ValidationError)` — default code: `"INVARIANT_VIOLATION"`
  - `NotFoundError(DomainError)` — default code: `"NOT_FOUND"`
  - `ConflictError(DomainError)` — default code: `"CONFLICT"`
  - `AlreadyExistsError(ConflictError)` — default code: `"ALREADY_EXISTS"`
  - `AlreadyDeletedError(ConflictError)` — default code: `"ALREADY_DELETED"`
  - `NotDeletedError(DomainError)` — default code: `"NOT_DELETED"`
  - `AuthorizationError(DomainError)` — default code: `"AUTHORIZATION_ERROR"`
  - `CurrencyMismatchError(DomainError)` — default code: `"CURRENCY_MISMATCH"`

**Tests to Create:**
- `tests/unit/shared_kernel/exceptions/__init__.py`
- `tests/unit/shared_kernel/exceptions/test_exceptions.py`
  - [ ] All exception types extend `DomainError`
  - [ ] Every exception carries `code` and `message`
  - [ ] Default codes match specification
  - [ ] Custom codes can override defaults
  - [ ] Exception hierarchy matches the defined tree exactly
  - [ ] `str()` representation includes message
  - [ ] Exceptions are catchable by parent type (e.g., `AlreadyDeletedError` caught by `ConflictError`)

**Acceptance Criteria:**
- [ ] All 11 exception types implemented
- [ ] Hierarchy matches spec tree exactly
- [ ] All tests pass

---

### Phase 3: Domain Layer — Value Objects

#### TASK-003: Implement Currency Enum

**Layer:** Domain
**Depends On:** TASK-002

**Description:**
Implement `Currency` as a Python `Enum` with 10 members. Each member carries `code`, `symbol`, `name`, and `decimal_places` attributes. Equality by `code`. Hashable.

**Files to Create:**
- `src/emerald/shared_kernel/value_objects/__init__.py` — Re-exports
- `src/emerald/shared_kernel/value_objects/currency.py` — `Currency` enum with all 10 currencies

**Tests to Create:**
- `tests/unit/shared_kernel/value_objects/__init__.py`
- `tests/unit/shared_kernel/value_objects/test_currency.py`
  - [ ] `Currency.USD.code` returns `"USD"`
  - [ ] `Currency.USD.decimal_places` returns `2`
  - [ ] `Currency.JPY.decimal_places` returns `0`
  - [ ] `Currency.USD == Currency.USD` is `True`
  - [ ] `Currency.USD == Currency.EUR` is `False`
  - [ ] All 10 currencies accessible as named constants
  - [ ] Currency members are hashable (usable in sets/dicts)

**Acceptance Criteria:**
- [ ] All 10 currencies defined with correct attributes
- [ ] All acceptance criteria from REQ-VO-002 satisfied
- [ ] All tests pass

---

#### TASK-004: Implement Money Value Object

**Layer:** Domain
**Depends On:** TASK-002, TASK-003

**Description:**
Implement `Money` as a `@dataclass(frozen=True)` with `amount: Decimal` and `currency: Currency`. Support arithmetic (`__add__`, `__sub__`, `__neg__`), comparison (`__lt__`, `__le__`, `__gt__`, `__ge__`), predicate methods (`is_zero`, `is_positive`, `is_negative`), Banker's rounding (`round_to_currency`), and a `Money.zero()` factory. All cross-currency operations raise `CurrencyMismatchError`. Construction with non-finite Decimal raises `InvalidValueError`.

**Implementation Notes:**
- Use `__post_init__` for validation (finite Decimal check)
- `__add__`/`__sub__` return new `Money` instances (immutable)
- Comparison operators enforce same-currency via `_ensure_same_currency` helper
- `round_to_currency()` uses `Decimal.quantize(ROUND_HALF_EVEN)` with currency's `decimal_places`

**Files to Create:**
- `src/emerald/shared_kernel/value_objects/money.py` — `Money` value object

**Tests to Create:**
- `tests/unit/shared_kernel/value_objects/test_money.py`
  - [ ] Addition of same-currency values
  - [ ] Addition of different currencies raises `CurrencyMismatchError`
  - [ ] Subtraction of same-currency values
  - [ ] Negation
  - [ ] `Money.zero()` factory
  - [ ] `is_zero()`, `is_positive()`, `is_negative()`
  - [ ] Comparison operators (lt, le, gt, ge) for same currency
  - [ ] Comparison across currencies raises `CurrencyMismatchError`
  - [ ] Banker's rounding: `.005` rounds down, `.015` rounds up
  - [ ] JPY rounding (0 decimal places)
  - [ ] Construction with NaN/Infinity raises `InvalidValueError`
  - [ ] Construction with negative amount is allowed
  - [ ] Equality: same amount + currency = equal
  - [ ] Hash: equal Money instances have same hash
  - [ ] Immutability: cannot reassign attributes

**Acceptance Criteria:**
- [ ] All 10 acceptance criteria from REQ-VO-001 satisfied
- [ ] All 5 business rules (BR-MONEY-001 through BR-MONEY-005) enforced
- [ ] All tests pass

---

#### TASK-005: Implement DateRange Value Object

**Layer:** Domain
**Depends On:** TASK-002

**Description:**
Implement `DateRange` as a `@dataclass(frozen=True)` with `start_date: date` and `end_date: date`. Both endpoints inclusive. Validate `start_date <= end_date` at construction. Methods: `contains(date)`, `overlaps(DateRange)`, `duration_days()`.

**Files to Create:**
- `src/emerald/shared_kernel/value_objects/date_range.py` — `DateRange` value object

**Tests to Create:**
- `tests/unit/shared_kernel/value_objects/test_date_range.py`
  - [ ] `contains()` for date within range
  - [ ] `contains()` for date outside range
  - [ ] `contains()` for start_date (inclusive)
  - [ ] `contains()` for end_date (inclusive)
  - [ ] `overlaps()` for overlapping ranges
  - [ ] `overlaps()` for non-overlapping ranges
  - [ ] `overlaps()` for adjacent ranges (same day boundary)
  - [ ] `duration_days()` returns inclusive count
  - [ ] Single-day range (`start == end`) has `duration_days() == 1`
  - [ ] Construction with `start_date > end_date` raises `InvalidValueError`
  - [ ] Equality and hashability

**Acceptance Criteria:**
- [ ] All 8 acceptance criteria from REQ-VO-003 satisfied
- [ ] Both business rules (BR-DR-001, BR-DR-002) enforced
- [ ] All tests pass

---

#### TASK-006: Implement RetentionPeriod Value Object

**Layer:** Domain
**Depends On:** TASK-002

**Description:**
Implement `RetentionUnit` enum (DAYS, MONTHS, YEARS) and `RetentionPeriod` as a `@dataclass(frozen=True)` with `duration: int` and `unit: RetentionUnit`. Validate `duration > 0`. Methods: `expiration_from(datetime)` using `dateutil.relativedelta` for calendar-accurate computation, `to_days()` for approximate days. Comparison operators use `to_days()`.

**Implementation Notes:**
- `expiration_from()` uses `relativedelta(days=d)`, `relativedelta(months=m)`, or `relativedelta(years=y)` depending on unit
- `to_days()` uses fixed approximation: 30 days/month, 365 days/year
- Comparison operators (`__lt__`, `__le__`, `__gt__`, `__ge__`) delegate to `to_days()`

**Files to Create:**
- `src/emerald/shared_kernel/value_objects/retention_period.py` — `RetentionUnit` enum + `RetentionPeriod` value object

**Tests to Create:**
- `tests/unit/shared_kernel/value_objects/test_retention_period.py`
  - [ ] `to_days()` for DAYS (30 days → 30)
  - [ ] `to_days()` for MONTHS (6 months → 180)
  - [ ] `to_days()` for YEARS (1 year → 365)
  - [ ] `expiration_from()` for DAYS
  - [ ] `expiration_from()` for MONTHS — month-end boundary (Jan 31 + 1 month → Feb 28/29)
  - [ ] `expiration_from()` for YEARS — leap year boundary (Feb 29 2024 + 1 year → Feb 28 2025)
  - [ ] Comparison operators between different units
  - [ ] Construction with `duration=0` raises `InvalidValueError`
  - [ ] Construction with `duration=-1` raises `InvalidValueError`
  - [ ] Equality and hashability
  - [ ] Returned datetime from `expiration_from()` is timezone-aware UTC

**Acceptance Criteria:**
- [ ] All 7 acceptance criteria from REQ-VO-004 satisfied
- [ ] All 4 business rules (BR-RP-001 through BR-RP-004) enforced
- [ ] All tests pass

---

### Phase 4: Domain Layer — Entity Traits

#### TASK-007: Implement Entity Base Class (Identity Trait)

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Implement `Entity` as a base class providing UUID-based identity. UUID generated at creation time (not by database). Immutable `id`. Identity-based equality (`__eq__` by `id` only) and `__hash__` by `id`.

**Implementation Notes:**
- Constructor accepts optional `id: UUID` parameter (default: `uuid.uuid4()`)
- `__eq__` checks `isinstance` and `id` equality
- `__hash__` returns `hash(self.id)`
- `id` is protected from reassignment (property with no setter, or `__setattr__` guard)

**Files to Create:**
- `src/emerald/shared_kernel/entities/__init__.py` — Re-exports
- `src/emerald/shared_kernel/entities/entity.py` — `Entity` base class

**Tests to Create:**
- `tests/unit/shared_kernel/entities/__init__.py`
- `tests/unit/shared_kernel/entities/test_entity.py`
  - [ ] Entity receives UUID at construction
  - [ ] Entity `id` cannot be reassigned
  - [ ] Two entities with same `id` are equal
  - [ ] Two entities with different `id` are not equal
  - [ ] Entity is hashable
  - [ ] Explicit `id` can be provided at construction

**Acceptance Criteria:**
- [ ] All 4 acceptance criteria from REQ-TRAIT-001 satisfied
- [ ] All 3 business rules (BR-ID-001 through BR-ID-003) enforced
- [ ] All tests pass

---

#### TASK-008: Implement TimestampedMixin

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Implement `TimestampedMixin` providing `created_at` and `updated_at` timestamps. Both are UTC timezone-aware. `created_at` is set once at creation and immutable. `updated_at` is set at creation and must be explicitly updated on state changes.

**Implementation Notes:**
- `created_at` is set via constructor (default: `datetime.now(UTC)`)
- `updated_at` is set via constructor (default: same as `created_at`)
- Provide a `_touch()` method that updates `updated_at` to current UTC time
- `created_at` protected from reassignment

**Files to Create:**
- `src/emerald/shared_kernel/entities/timestamped.py` — `TimestampedMixin`

**Tests to Create:**
- `tests/unit/shared_kernel/entities/test_timestamped.py`
  - [ ] `created_at` is set at construction
  - [ ] `created_at` is immutable (cannot be reassigned)
  - [ ] `updated_at` is set at construction
  - [ ] `updated_at` changes when `_touch()` is called
  - [ ] Both timestamps carry UTC timezone info
  - [ ] Naive datetimes are not accepted (or converted to UTC)

**Acceptance Criteria:**
- [ ] All 3 acceptance criteria from REQ-TRAIT-002 satisfied
- [ ] All 3 business rules (BR-TS-001 through BR-TS-003) enforced
- [ ] All tests pass

---

#### TASK-009: Implement SoftDeletableMixin

**Layer:** Domain
**Depends On:** TASK-002, TASK-006

**Description:**
Implement `SoftDeletableMixin` providing `deleted_at`, `deleted_by`, `deletion_reason`, and `hard_delete_scheduled_at` fields. Methods: `soft_delete(deleted_by, reason, retention)`, `recover()`, `is_deleted()`, `is_active()`.

**Implementation Notes:**
- All four fields default to `None`
- `soft_delete()` raises `AlreadyDeletedError` if already deleted
- `soft_delete()` sets `deleted_at` = `datetime.now(UTC)`, `deleted_by`, `deletion_reason`, and `hard_delete_scheduled_at` via `retention.expiration_from(deleted_at)`
- `recover()` raises `NotDeletedError` if not deleted
- `recover()` clears all four fields to `None`
- `is_deleted()` returns `deleted_at is not None`
- `is_active()` returns `not is_deleted()`

**Files to Create:**
- `src/emerald/shared_kernel/entities/soft_deletable.py` — `SoftDeletableMixin`

**Tests to Create:**
- `tests/unit/shared_kernel/entities/test_soft_deletable.py`
  - [ ] `soft_delete()` sets `deleted_at`, `deleted_by`, `hard_delete_scheduled_at`
  - [ ] `soft_delete()` with optional `reason`
  - [ ] `soft_delete()` on already-deleted raises `AlreadyDeletedError`
  - [ ] `recover()` clears all deletion fields
  - [ ] `recover()` on active entity raises `NotDeletedError`
  - [ ] `is_deleted()` and `is_active()` reflect state correctly
  - [ ] `hard_delete_scheduled_at` is calendar-accurate from retention period
  - [ ] Timestamps are UTC timezone-aware

**Acceptance Criteria:**
- [ ] All 7 acceptance criteria from REQ-TRAIT-003 satisfied
- [ ] All 7 business rules (BR-SD-001 through BR-SD-007) enforced
- [ ] All tests pass

---

#### TASK-010: Implement AuditableMixin

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Implement `AuditableMixin` providing `created_by: UUID` and `updated_by: UUID`. `created_by` is set once at creation and immutable. `updated_by` is updated on state changes.

**Implementation Notes:**
- `created_by` set via constructor parameter (required)
- `updated_by` set via constructor parameter (defaults to same as `created_by`)
- Provide `_set_updated_by(actor_id: UUID)` method
- `created_by` protected from reassignment

**Files to Create:**
- `src/emerald/shared_kernel/entities/auditable.py` — `AuditableMixin`

**Tests to Create:**
- `tests/unit/shared_kernel/entities/test_auditable.py`
  - [ ] `created_by` is set at construction
  - [ ] `created_by` is immutable
  - [ ] `updated_by` can be changed via `_set_updated_by()`
  - [ ] `updated_by` defaults to `created_by` at construction

**Acceptance Criteria:**
- [ ] All 2 acceptance criteria from REQ-TRAIT-004 satisfied
- [ ] Both business rules (BR-AUD-001, BR-AUD-002) enforced
- [ ] All tests pass

---

### Phase 5: Domain Layer — Events & Aggregate Root

#### TASK-011: Implement DomainEvent Base

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Implement `DomainEvent` as a `@dataclass(frozen=True)` base class with `event_id: UUID`, `occurred_at: datetime` (UTC, timezone-aware), `aggregate_id: UUID`, and `aggregate_type: str`. Events are immutable. `event_id` generated at creation; `occurred_at` defaults to `datetime.now(UTC)`.

**Files to Create:**
- `src/emerald/shared_kernel/events/__init__.py` — Re-exports
- `src/emerald/shared_kernel/events/domain_event.py` — `DomainEvent` base class

**Tests to Create:**
- `tests/unit/shared_kernel/events/__init__.py`
- `tests/unit/shared_kernel/events/test_domain_event.py`
  - [ ] DomainEvent is immutable (frozen dataclass)
  - [ ] `event_id` is a UUID, unique per instance
  - [ ] `occurred_at` is timezone-aware UTC
  - [ ] `aggregate_id` and `aggregate_type` are set at creation
  - [ ] Concrete event subclass inherits base attributes
  - [ ] Events with same data but different `event_id` are not equal

**Acceptance Criteria:**
- [ ] All 4 acceptance criteria from REQ-EVT-001 satisfied
- [ ] All 5 business rules (BR-EVT-001 through BR-EVT-005) enforced
- [ ] All tests pass

---

#### TASK-012: Implement AggregateRoot Base

**Layer:** Domain
**Depends On:** TASK-007, TASK-008, TASK-011

**Description:**
Implement `AggregateRoot` combining `Entity` (Identity) and `TimestampedMixin`, plus domain event collection. Provides `_register_event(event)` for internal use and `collect_events()` that returns events in order and clears the list.

**Implementation Notes:**
- `AggregateRoot` inherits from `Entity` and `TimestampedMixin`
- Internal `_events: list[DomainEvent]` list
- `_register_event()` appends to `_events`
- `collect_events()` returns copy of list and clears it
- Concrete aggregate roots add SoftDeletable/Auditable as needed via additional inheritance

**Files to Create:**
- `src/emerald/shared_kernel/entities/aggregate_root.py` — `AggregateRoot` base class

**Tests to Create:**
- `tests/unit/shared_kernel/entities/test_aggregate_root.py`
  - [ ] AggregateRoot has `id`, `created_at`, `updated_at`
  - [ ] `_register_event()` adds events to internal list
  - [ ] `collect_events()` returns events in registration order
  - [ ] `collect_events()` clears internal list after returning
  - [ ] Second `collect_events()` without new events returns empty list
  - [ ] AggregateRoot has identity-based equality (from Entity)

**Acceptance Criteria:**
- [ ] All 5 acceptance criteria from REQ-AGG-001 satisfied
- [ ] All 4 business rules (BR-AGG-001 through BR-AGG-004) enforced
- [ ] All tests pass

---

### Phase 6: Package Exports & Integration

#### TASK-013: Configure Package Public API

**Layer:** Domain
**Depends On:** TASK-002 through TASK-012

**Description:**
Populate all `__init__.py` files with explicit re-exports to create a clean public API. Developers should be able to import everything from `emerald.shared_kernel` directly.

**Files to Modify:**
- `src/emerald/shared_kernel/__init__.py` — Re-export all public types:
  - Value Objects: `Money`, `Currency`, `DateRange`, `RetentionPeriod`, `RetentionUnit`
  - Entity Bases: `Entity`, `AggregateRoot`
  - Mixins: `TimestampedMixin`, `SoftDeletableMixin`, `AuditableMixin`
  - Events: `DomainEvent`
  - Exceptions: `DomainError`, `ValidationError`, `InvalidValueError`, `InvariantViolationError`, `NotFoundError`, `ConflictError`, `AlreadyExistsError`, `AlreadyDeletedError`, `NotDeletedError`, `AuthorizationError`, `CurrencyMismatchError`
- `src/emerald/shared_kernel/value_objects/__init__.py` — Re-export VOs
- `src/emerald/shared_kernel/entities/__init__.py` — Re-export entities/mixins
- `src/emerald/shared_kernel/events/__init__.py` — Re-export events
- `src/emerald/shared_kernel/exceptions/__init__.py` — Re-export exceptions

**Tests to Create:**
- Verify all public types are importable from `emerald.shared_kernel`

**Acceptance Criteria:**
- [ ] `from emerald.shared_kernel import Money, Currency, Entity, AggregateRoot, DomainEvent, DomainError` works
- [ ] All public types listed in `__all__` for each module
- [ ] No circular imports

---

### Phase 7: Verification & Quality

#### TASK-014: Run Full Test Suite and Quality Checks

**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-013

**Description:**
Run the complete test suite, linter, formatter, and type checker to verify everything works end-to-end.

**Verification Steps:**
- [ ] `uv run pytest tests/unit/shared_kernel/ -v` — all tests pass
- [ ] `uv run ruff check .` — no linting errors
- [ ] `uv run ruff format --check .` — formatting consistent
- [ ] `uv run ty check` — no type errors
- [ ] No circular imports
- [ ] Zero framework dependencies in `src/emerald/shared_kernel/` (verify no imports of SQLAlchemy, FastAPI, etc.)

**Acceptance Criteria:**
- [ ] All tests pass (target: 100% pass rate)
- [ ] Zero linting errors
- [ ] Zero type errors
- [ ] Clean formatting

---

## 5. Task Dependency Graph

```
TASK-001 (Project Bootstrap)
    │
    ├──► TASK-002 (Exceptions) ──────────────────────────────────────────┐
    │        │                                                           │
    │        ├──► TASK-003 (Currency) ──┐                                │
    │        │                          ├──► TASK-004 (Money)            │
    │        │                          │                                │
    │        ├──► TASK-005 (DateRange)  │                                │
    │        │                          │                                │
    │        └──► TASK-006 (RetentionPeriod)                             │
    │                  │                                                 │
    │                  └─────────────────────► TASK-009 (SoftDeletable)  │
    │                                                                    │
    ├──► TASK-007 (Entity/Identity) ─────────┐                          │
    │                                         │                          │
    ├──► TASK-008 (Timestamped) ─────────────┤                          │
    │                                         │                          │
    ├──► TASK-010 (Auditable)                ├──► TASK-012 (AggregateRoot)
    │                                         │         │
    └──► TASK-011 (DomainEvent) ─────────────┘         │
                                                        │
                                              TASK-013 (Package Exports)
                                                        │
                                              TASK-014 (Full Verification)
```

**Parallelization Opportunities:**
- TASK-003, TASK-005, TASK-006 can run in parallel (all depend only on TASK-002)
- TASK-007, TASK-008, TASK-010, TASK-011 can run in parallel (all depend only on TASK-001)
- TASK-004 depends on TASK-003 (Currency needed for Money)
- TASK-009 depends on TASK-002 + TASK-006 (exceptions + RetentionPeriod)
- TASK-012 depends on TASK-007 + TASK-008 + TASK-011

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `dateutil.relativedelta` edge cases in month-end arithmetic | Low | Medium | Comprehensive edge-case tests for month-end boundaries, leap years. Library is battle-tested. |
| Decimal precision issues in Money arithmetic | Low | High | Exhaustive Banker's rounding tests. Never use `float`. Parametric tests with known edge cases. |
| Multiple inheritance MRO conflicts with entity traits | Medium | Medium | Keep traits focused (single responsibility). Test trait composition explicitly. Use cooperative `super()` calls. |
| Circular imports between subpackages | Low | Low | Clean dependency direction: exceptions ← value_objects ← entities. No reverse imports. |
| `python-dateutil` compatibility with Python 3.13 | Low | Medium | Verify in TASK-001 during `uv sync`. Fall back to manual implementation if needed. |
| Entity `__setattr__` override conflicts with dataclass or mixin initialization | Medium | Medium | Careful `__init__` design — allow setting during construction, protect after. Test thoroughly. |

---

## 7. Definition of Done

- [ ] All 14 tasks completed
- [ ] All acceptance criteria from spec met (39 checkboxes from spec)
- [ ] All unit tests passing
- [ ] `uv run ruff check .` clean
- [ ] `uv run ruff format --check .` clean
- [ ] `uv run ty check` clean
- [ ] Zero external framework dependencies in shared kernel code
- [ ] All public types importable from `emerald.shared_kernel`
- [ ] All value objects are immutable (frozen dataclasses)
- [ ] All entity equality is identity-based
- [ ] All timestamps are UTC timezone-aware
- [ ] All monetary operations use `Decimal` (never `float`)
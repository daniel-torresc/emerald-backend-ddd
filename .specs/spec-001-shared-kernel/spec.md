# Shared Kernel Specification

**Version:** 1.0
**Status:** Implemented
**Date:** 2026-02-05

---

## 1. Overview

The Shared Kernel provides the foundational building blocks used across all bounded contexts in the Emerald Finance Platform. It contains base entity traits, an aggregate root base type, common value objects, domain event infrastructure, and a domain exception hierarchy. Every other specification depends on these primitives.

**Key Principle:** The Shared Kernel is intentionally small. Only concepts that are truly shared across multiple bounded contexts belong here. Context-specific value objects (e.g., `PermissionLevel`, `AccountName`, `EmailAddress`) belong in their respective contexts.

---

## 2. Background & Context

### Problem Statement

Every bounded context (IAM, Core Finance, Classification, External Integrations) needs consistent patterns for entity identity, timestamps, soft deletion, monetary calculations, and event-driven communication. Without a shared kernel, each context would re-invent these fundamentals, leading to inconsistencies and integration friction.

### Business Goals

- Establish a single, authoritative set of foundational types for the entire platform
- Ensure all monetary calculations use arbitrary-precision arithmetic (never floating point)
- Provide consistent soft-deletion and audit tracking across all entities
- Enable event-driven communication between bounded contexts through a shared event infrastructure

### Success Metrics

- All bounded contexts use shared kernel types (no duplicate Money, Currency, or entity base types)
- Zero floating-point arithmetic in monetary operations
- All entities consistently track creation time, modification time, and actor identity
- Domain events follow a uniform structure across all contexts

---

## 3. Scope

### In Scope

- Base entity traits: Identity, Timestamped, Soft-Deletable, Auditable
- Aggregate root base type combining Identity + Timestamped + event collection
- Common value objects: `Money`, `Currency`, `DateRange`, `RetentionPeriod`
- Domain event base infrastructure (base event type + event collection pattern)
- Domain exception base hierarchy

### Out of Scope

- Context-specific value objects (`EmailAddress`, `IBAN`, `TaxonomyPath`, `PermissionLevel`)
- Repository interfaces (each context defines its own)
- Application layer concerns (use cases, command/query handlers)
- Event dispatching/bus mechanism (application layer concern)
- Full audit logging infrastructure (see Spec 016)
- Pagination, sorting, or query abstractions (see Spec 018)

---

## 4. Users & Personas

### Primary Users

The Shared Kernel is consumed by **developers building bounded contexts**, not end users directly. It provides the type system and behavioral contracts that all domain code builds upon.

### User Goals

- Consistent entity modeling across bounded contexts
- Safe monetary arithmetic that prevents currency mismatch and precision loss
- Uniform soft-deletion behavior with retention scheduling
- Reliable domain event infrastructure for inter-context communication

---

## 5. Requirements

### 5.1 Value Objects

All value objects in the Shared Kernel are **immutable** and implement **equality by value** (two instances with the same attributes are equal). They are hashable and safe for use in sets and as dictionary keys.

---

#### REQ-VO-001: Money Value Object

**Priority:** Must Have

A monetary amount paired with its currency. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| amount | Decimal | The monetary amount (arbitrary precision, never float) |
| currency | Currency | The currency of this money |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__add__(other: Money) -> Money` | Add two Money values | `CurrencyMismatchError` if currencies differ |
| `__sub__(other: Money) -> Money` | Subtract two Money values | `CurrencyMismatchError` if currencies differ |
| `__neg__() -> Money` | Negate the amount | — |
| `__eq__(other: Money) -> bool` | Equality by amount and currency | — |
| `__lt__(other: Money) -> bool` | Less-than comparison | `CurrencyMismatchError` if currencies differ |
| `__le__(other: Money) -> bool` | Less-than-or-equal comparison | `CurrencyMismatchError` if currencies differ |
| `__gt__(other: Money) -> bool` | Greater-than comparison | `CurrencyMismatchError` if currencies differ |
| `__ge__(other: Money) -> bool` | Greater-than-or-equal comparison | `CurrencyMismatchError` if currencies differ |
| `is_zero() -> bool` | Whether amount equals zero | — |
| `is_positive() -> bool` | Whether amount is greater than zero | — |
| `is_negative() -> bool` | Whether amount is less than zero | — |
| `round_to_currency() -> Money` | Round to currency's decimal places using Banker's rounding (ROUND_HALF_EVEN) | — |

**Construction:**

| Constructor | Description | Raises |
|-------------|-------------|--------|
| `Money(amount: Decimal, currency: Currency)` | Standard constructor | `InvalidValueError` if amount is not a finite Decimal |
| `Money.zero(currency: Currency)` | Convenience: create zero-amount Money | — |

**Business Rules:**

- BR-MONEY-001: Arithmetic operations (add, subtract) only allowed between same-currency values; raises `CurrencyMismatchError` otherwise
- BR-MONEY-002: Comparison operators (lt, le, gt, ge) only allowed between same-currency values; raises `CurrencyMismatchError` otherwise
- BR-MONEY-003: Amount must use `Decimal` type — floating-point types (`float`) are never acceptable
- BR-MONEY-004: `round_to_currency()` uses **Banker's rounding** (`ROUND_HALF_EVEN`) and rounds to the currency's `decimal_places` (e.g., 2 for USD, 0 for JPY)
- BR-MONEY-005: Amount must be a finite Decimal (not NaN, not Infinity)

**Acceptance Criteria:**

- [ ] `Money(Decimal("10.00"), Currency.USD) + Money(Decimal("5.00"), Currency.USD)` returns `Money(Decimal("15.00"), Currency.USD)`
- [ ] `Money(Decimal("10.00"), Currency.USD) + Money(Decimal("5.00"), Currency.EUR)` raises `CurrencyMismatchError`
- [ ] `Money(Decimal("10.00"), Currency.USD) < Money(Decimal("20.00"), Currency.EUR)` raises `CurrencyMismatchError`
- [ ] `-Money(Decimal("10.00"), Currency.USD)` returns `Money(Decimal("-10.00"), Currency.USD)`
- [ ] `Money.zero(Currency.USD).is_zero()` returns `True`
- [ ] `Money(Decimal("10.005"), Currency.USD).round_to_currency()` returns `Money(Decimal("10.00"), Currency.USD)` (Banker's rounding: .005 rounds down)
- [ ] `Money(Decimal("10.015"), Currency.USD).round_to_currency()` returns `Money(Decimal("10.02"), Currency.USD)` (Banker's rounding: .015 rounds up)
- [ ] `Money(Decimal("100"), Currency.JPY).round_to_currency()` returns `Money(Decimal("100"), Currency.JPY)` (0 decimal places)
- [ ] Constructing with `float` amount raises `InvalidValueError` or is rejected by type system
- [ ] Two `Money` instances with same amount and currency are equal and have same hash

---

#### REQ-VO-002: Currency Value Object

**Priority:** Must Have

An ISO 4217 currency. Immutable. Implemented as a **static enum** — the set of supported currencies is defined in code.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| code | str | ISO 4217 3-letter code (e.g., "USD", "EUR") |
| symbol | str | Display symbol (e.g., "$", "€") |
| name | str | Full name (e.g., "US Dollar") |
| decimal_places | int | Standard decimal places (e.g., 2 for USD, 0 for JPY) |

**Behavior:**

| Method | Description |
|--------|-------------|
| `__eq__(other: Currency) -> bool` | Equality by code |
| `__hash__() -> int` | Hashable by code |

**Initial Currency Set (10 currencies):**

| Code | Symbol | Name | Decimal Places |
|------|--------|------|----------------|
| USD | $ | US Dollar | 2 |
| EUR | € | Euro | 2 |
| GBP | £ | British Pound | 2 |
| JPY | ¥ | Japanese Yen | 0 |
| CHF | CHF | Swiss Franc | 2 |
| CAD | C$ | Canadian Dollar | 2 |
| AUD | A$ | Australian Dollar | 2 |
| MXN | MX$ | Mexican Peso | 2 |
| BRL | R$ | Brazilian Real | 2 |
| CNY | ¥ | Chinese Yuan | 2 |

**Business Rules:**

- BR-CUR-001: Code must be a valid 3-letter ISO 4217 code
- BR-CUR-002: The initial set contains 10 currencies; additional currencies are added via code changes as needed
- BR-CUR-003: Currency equality is determined solely by the `code` attribute

**Acceptance Criteria:**

- [ ] `Currency.USD.code` returns `"USD"`
- [ ] `Currency.USD.decimal_places` returns `2`
- [ ] `Currency.JPY.decimal_places` returns `0`
- [ ] `Currency.USD == Currency.USD` is `True`
- [ ] `Currency.USD == Currency.EUR` is `False`
- [ ] All 10 initial currencies are accessible as named constants

---

#### REQ-VO-003: DateRange Value Object

**Priority:** Must Have

A time period between two dates. Both endpoints are inclusive. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| start_date | date | Start of range (inclusive) |
| end_date | date | End of range (inclusive) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `contains(d: date) -> bool` | Whether date falls within range (inclusive) | — |
| `overlaps(other: DateRange) -> bool` | Whether two ranges share any dates | — |
| `duration_days() -> int` | Number of days in range (inclusive count) | — |

**Business Rules:**

- BR-DR-001: `start_date` must be less than or equal to `end_date`; raises `InvalidValueError` otherwise
- BR-DR-002: Both `start_date` and `end_date` are inclusive in all operations

**Acceptance Criteria:**

- [ ] `DateRange(date(2025, 1, 1), date(2025, 1, 31)).contains(date(2025, 1, 15))` is `True`
- [ ] `DateRange(date(2025, 1, 1), date(2025, 1, 31)).contains(date(2025, 2, 1))` is `False`
- [ ] `DateRange(date(2025, 1, 1), date(2025, 1, 31)).contains(date(2025, 1, 1))` is `True` (inclusive start)
- [ ] `DateRange(date(2025, 1, 1), date(2025, 1, 31)).contains(date(2025, 1, 31))` is `True` (inclusive end)
- [ ] Two overlapping ranges return `True` for `overlaps()`
- [ ] Two non-overlapping ranges return `False` for `overlaps()`
- [ ] `DateRange(date(2025, 1, 1), date(2025, 1, 31)).duration_days()` returns `31`
- [ ] Constructing with `start_date > end_date` raises `InvalidValueError`

---

#### REQ-VO-004: RetentionPeriod Value Object

**Priority:** Must Have

A duration for data retention policies. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| duration | int | Numeric duration value (must be positive) |
| unit | RetentionUnit | DAYS, MONTHS, or YEARS |

**Enum — RetentionUnit:**

| Value | Description |
|-------|-------------|
| DAYS | Duration in days |
| MONTHS | Duration in calendar months |
| YEARS | Duration in calendar years |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `expiration_from(start: datetime) -> datetime` | Calculate calendar-accurate expiration date from a start time | — |
| `to_days() -> int` | Approximate total days (30 days/month, 365 days/year) — for display/logging only | — |
| `__eq__`, `__lt__`, `__gt__`, `__le__`, `__ge__` | Comparison by approximate total days | — |

**Business Rules:**

- BR-RP-001: `duration` must be a positive integer; raises `InvalidValueError` otherwise
- BR-RP-002: `expiration_from()` uses **calendar-accurate** computation — e.g., 1 month from Jan 31 = Feb 28 (or 29 in leap year). This is the authoritative method for scheduling hard deletes.
- BR-RP-003: `to_days()` uses fixed approximation (30 days/month, 365 days/year) and is intended for display/comparison purposes only, not for scheduling.
- BR-RP-004: Comparison operators use `to_days()` approximation for ordering.

**Acceptance Criteria:**

- [ ] `RetentionPeriod(30, RetentionUnit.DAYS).to_days()` returns `30`
- [ ] `RetentionPeriod(6, RetentionUnit.MONTHS).to_days()` returns `180`
- [ ] `RetentionPeriod(1, RetentionUnit.YEARS).to_days()` returns `365`
- [ ] `RetentionPeriod(1, RetentionUnit.MONTHS).expiration_from(datetime(2025, 1, 31, ...))` returns a datetime in February (calendar-accurate)
- [ ] `RetentionPeriod(30, RetentionUnit.DAYS) < RetentionPeriod(6, RetentionUnit.MONTHS)` is `True`
- [ ] Constructing with `duration=0` raises `InvalidValueError`
- [ ] Constructing with `duration=-1` raises `InvalidValueError`

---

### 5.2 Base Entity Traits

Entity traits are composable building blocks. Each trait provides a distinct capability that can be mixed into domain entities.

---

#### REQ-TRAIT-001: Entity Identity

**Priority:** Must Have

All entities have a UUID-based identity assigned at creation.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique identifier, assigned at creation |

**Business Rules:**

- BR-ID-001: Entity IDs are UUIDs generated at entity creation time (not by the database)
- BR-ID-002: Entity IDs are immutable once assigned
- BR-ID-003: Two entities of the same type are equal if and only if their IDs are equal (identity equality, not attribute equality)

**Acceptance Criteria:**

- [ ] Entities receive a UUID at construction time
- [ ] Entity `id` cannot be reassigned after construction
- [ ] Two entities with the same `id` are considered equal regardless of other attribute values
- [ ] Two entities with different `id` values are not equal even if all other attributes match

---

#### REQ-TRAIT-002: Timestamped Entity

**Priority:** Must Have

All entities track creation and modification times in UTC.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| created_at | datetime (UTC, timezone-aware) | No | When the entity was created |
| updated_at | datetime (UTC, timezone-aware) | Auto | When the entity was last modified |

**Business Rules:**

- BR-TS-001: `created_at` is set once at entity creation and never changes
- BR-TS-002: `updated_at` is automatically set on every state change
- BR-TS-003: All timestamps are in UTC with timezone awareness (`datetime` with `tzinfo` set)

**Acceptance Criteria:**

- [ ] `created_at` is set at construction and is immutable
- [ ] `updated_at` changes whenever entity state is modified
- [ ] Both timestamps carry UTC timezone info (not naive datetimes)

---

#### REQ-TRAIT-003: Soft-Deletable Entity

**Priority:** Must Have

Entities that support soft deletion. Soft delete marks an entity as deleted without removing it, allowing recovery within a retention window.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| deleted_at | datetime? | Yes | When soft delete occurred (`None` = active) |
| deleted_by | UUID? | Yes | Who performed the deletion |
| deletion_reason | str? | Yes | Optional reason for deletion |
| hard_delete_scheduled_at | datetime? | Yes | When automatic hard delete will occur |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `soft_delete(deleted_by: UUID, reason: str?, retention: RetentionPeriod) -> None` | Mark as soft deleted and schedule hard deletion | `AlreadyDeletedError` if already deleted |
| `recover() -> None` | Restore from soft-deleted state | `NotDeletedError` if not deleted |
| `is_deleted() -> bool` | Whether entity is currently soft deleted | — |
| `is_active() -> bool` | Whether entity is active (not deleted) | — |

**Business Rules:**

- BR-SD-001: `soft_delete()` sets `deleted_at` to current UTC time, `deleted_by` to the actor, and optionally `deletion_reason`
- BR-SD-002: `hard_delete_scheduled_at` is calculated as `deleted_at + retention` using `RetentionPeriod.expiration_from()`
- BR-SD-003: `soft_delete()` raises `AlreadyDeletedError` if the entity is already soft deleted
- BR-SD-004: `recover()` clears all four deletion-related fields (`deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`)
- BR-SD-005: `recover()` raises `NotDeletedError` if the entity is not soft deleted
- BR-SD-006: Whether a child entity can be recovered when its parent is deleted is enforced by the aggregate root, not by this trait
- BR-SD-007: The `retention` parameter is provided by the application layer, which resolves the correct retention policy for the entity type

**Acceptance Criteria:**

- [ ] `soft_delete()` sets `deleted_at`, `deleted_by`, and `hard_delete_scheduled_at`
- [ ] `soft_delete()` on an already-deleted entity raises `AlreadyDeletedError`
- [ ] `recover()` clears all deletion fields
- [ ] `recover()` on an active entity raises `NotDeletedError`
- [ ] After `soft_delete()`, `is_deleted()` returns `True` and `is_active()` returns `False`
- [ ] After `recover()`, `is_deleted()` returns `False` and `is_active()` returns `True`
- [ ] `hard_delete_scheduled_at` is calendar-accurate based on retention period

---

#### REQ-TRAIT-004: Auditable Entity

**Priority:** Must Have

Entities that track which actor created and last modified them. Rich audit context (IP address, user agent, request ID, before/after state) is handled by the Audit Logging infrastructure (Spec 016), not this trait.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| created_by | UUID | No | Who created this entity |
| updated_by | UUID | Auto | Who last modified this entity |

**Business Rules:**

- BR-AUD-001: `created_by` is set once at entity creation and never changes
- BR-AUD-002: `updated_by` is set on every state change to reflect the current actor

**Acceptance Criteria:**

- [ ] `created_by` is set at construction and is immutable
- [ ] `updated_by` changes when entity state is modified

---

### 5.3 Aggregate Root Base

#### REQ-AGG-001: AggregateRoot Base Type

**Priority:** Must Have

All aggregate roots share a common base that combines entity identity, timestamps, and domain event collection. This ensures consistent behavior across all bounded contexts.

**Composed From:**

- Entity Identity (REQ-TRAIT-001)
- Timestamped Entity (REQ-TRAIT-002)

**Additional Behavior — Event Collection:**

| Method | Description |
|--------|-------------|
| `_register_event(event: DomainEvent) -> None` | Add an event to the internal collection (called by aggregate methods) |
| `collect_events() -> list[DomainEvent]` | Return all accumulated events and clear the internal list |

**Business Rules:**

- BR-AGG-001: Events are collected internally and not persisted as part of the aggregate state
- BR-AGG-002: `collect_events()` returns events in the order they were registered and clears the internal list
- BR-AGG-003: The application layer calls `collect_events()` after successful persistence and dispatches the events
- BR-AGG-004: Aggregate roots that need soft-deletion or auditability compose those traits in addition to this base

**Acceptance Criteria:**

- [ ] AggregateRoot has `id`, `created_at`, `updated_at` from composed traits
- [ ] Domain methods can register events internally via `_register_event()`
- [ ] `collect_events()` returns all registered events in order
- [ ] `collect_events()` clears the internal event list after returning
- [ ] Calling `collect_events()` twice without new events returns an empty list on second call

---

### 5.4 Domain Event Infrastructure

#### REQ-EVT-001: Base Domain Event

**Priority:** Must Have

All domain events share a common base structure.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| event_id | UUID | Unique event identifier |
| occurred_at | datetime (UTC, timezone-aware) | When the event occurred |
| aggregate_id | UUID | ID of the aggregate that produced the event |
| aggregate_type | str | Type name of the aggregate (e.g., "Account", "User") |

**Business Rules:**

- BR-EVT-001: Domain events are immutable records of something that happened
- BR-EVT-002: Events are named in past tense (e.g., `AccountCreated`, `TransactionSplit`)
- BR-EVT-003: Events carry only the data needed by consumers — no full entity dumps
- BR-EVT-004: `event_id` is generated at event creation time
- BR-EVT-005: `occurred_at` is UTC with timezone awareness

**Acceptance Criteria:**

- [ ] Domain events are immutable after creation
- [ ] Domain events carry `event_id`, `occurred_at`, `aggregate_id`, `aggregate_type`
- [ ] `event_id` is a unique UUID
- [ ] `occurred_at` is timezone-aware UTC

---

### 5.5 Domain Exception Hierarchy

#### REQ-EXC-001: Exception Base Types

**Priority:** Must Have

A structured exception hierarchy for domain-level errors. All domain exceptions carry a machine-readable `code` and a human-readable `message`.

**Hierarchy:**

```
DomainError (base)
├── ValidationError
│   ├── InvalidValueError          # Value object construction failure
│   └── InvariantViolationError    # Aggregate invariant broken
├── NotFoundError                  # Entity not found
├── ConflictError                  # Uniqueness or state conflict
│   ├── AlreadyExistsError         # Duplicate entity
│   └── AlreadyDeletedError        # Operation on deleted entity
├── NotDeletedError                # Recovery on non-deleted entity
├── AuthorizationError             # Domain-level permission denied
└── CurrencyMismatchError          # Cross-currency operation attempted
```

**Base Attributes (all exceptions):**

| Attribute | Type | Description |
|-----------|------|-------------|
| code | str | Machine-readable error code (e.g., `"CURRENCY_MISMATCH"`) |
| message | str | Human-readable error description |

**Business Rules:**

- BR-EXC-001: All domain exceptions inherit from `DomainError`
- BR-EXC-002: Domain exceptions are raised in the domain layer
- BR-EXC-003: Translation to HTTP responses (status codes, error bodies) happens in the presentation layer, not the domain
- BR-EXC-004: Each exception type has a default `code` that can be overridden at construction

**Acceptance Criteria:**

- [ ] All exception types extend `DomainError`
- [ ] Every exception carries `code` and `message`
- [ ] `CurrencyMismatchError` is raised by Money arithmetic with different currencies
- [ ] `AlreadyDeletedError` is raised by `soft_delete()` on a deleted entity
- [ ] `NotDeletedError` is raised by `recover()` on an active entity
- [ ] `InvalidValueError` is raised by value object constructors on invalid input
- [ ] `InvariantViolationError` is raised when an aggregate invariant is violated
- [ ] Exception hierarchy matches the defined tree exactly

---

### 5.6 Non-Functional Requirements

#### Performance

- Value object construction and arithmetic must have negligible overhead (no I/O)
- Decimal arithmetic is acceptable despite being slower than float — correctness is mandatory

#### Security

- No security concerns at the shared kernel level — all types are pure domain concepts
- Money values never use floating-point to prevent financial rounding vulnerabilities

#### Scalability

- All types are stateless and thread-safe (immutable value objects, no shared mutable state)

#### Testability

- The entire shared kernel has **zero framework dependencies** — pure Python only
- 100% unit testable without any infrastructure (no database, no network, no file system)

---

## 6. User Stories

### US-001: Same-Currency Arithmetic

**As a** developer building the Account aggregate
**I want** Money to support addition and subtraction for same-currency values
**So that** I can calculate account balances safely

**Acceptance Criteria:**
- [ ] Given two Money values in USD, when added, then the result is a Money in USD with the sum amount
- [ ] Given two Money values in different currencies, when added, then CurrencyMismatchError is raised

### US-002: Soft Delete Lifecycle

**As a** developer implementing entity deletion
**I want** a reusable soft-delete trait with retention scheduling
**So that** all entities follow the same deletion lifecycle consistently

**Acceptance Criteria:**
- [ ] Given an active entity, when soft_delete() is called with a retention period, then deleted_at, deleted_by, and hard_delete_scheduled_at are set
- [ ] Given a soft-deleted entity, when recover() is called, then all deletion fields are cleared
- [ ] Given a soft-deleted entity, when soft_delete() is called again, then AlreadyDeletedError is raised

### US-003: Domain Event Collection

**As a** developer building aggregate roots
**I want** aggregates to collect domain events during state changes
**So that** events can be dispatched after successful persistence

**Acceptance Criteria:**
- [ ] Given an aggregate root, when a domain method registers events, then collect_events() returns those events in order
- [ ] Given an aggregate root after collect_events(), when collect_events() is called again, then an empty list is returned

### US-004: Retention Period Calculation

**As a** developer implementing data lifecycle management
**I want** RetentionPeriod to calculate calendar-accurate expiration dates
**So that** hard delete scheduling is correct across month and year boundaries

**Acceptance Criteria:**
- [ ] Given RetentionPeriod(1, MONTHS) and start date Jan 31, when expiration_from() is called, then the result is Feb 28 (or 29 in leap year)
- [ ] Given RetentionPeriod(1, YEARS) and start date Feb 29 2024, when expiration_from() is called, then the result is Feb 28 2025

---

## 7. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Money addition with different currencies | Raises `CurrencyMismatchError` |
| Money comparison with different currencies | Raises `CurrencyMismatchError` |
| Money constructed with NaN or Infinity | Raises `InvalidValueError` |
| Money constructed with negative amount | Allowed — negative amounts represent debits/expenses |
| DateRange with start_date > end_date | Raises `InvalidValueError` at construction |
| DateRange with start_date == end_date | Allowed — represents a single day; `duration_days()` returns `1` |
| RetentionPeriod with duration 0 or negative | Raises `InvalidValueError` at construction |
| soft_delete() on already-deleted entity | Raises `AlreadyDeletedError` |
| recover() on active (non-deleted) entity | Raises `NotDeletedError` |
| collect_events() called twice without new events | Returns empty list on second call |
| RetentionPeriod expiration across DST boundaries | No impact — all timestamps are UTC |
| RetentionPeriod expiration on month-end boundaries | Calendar-accurate: 1 month from Jan 31 = Feb 28/29 |

---

## 8. Dependencies

### Internal Dependencies

- **None** — the Shared Kernel is the foundation with zero dependencies on other specs

### Downstream Dependents (Blocks)

- Spec 002: User Registration & Identity
- Spec 006: Data Lifecycle Management
- Spec 007: Account Management
- Spec 013: Classification & Taxonomies
- Spec 016: Audit Logging
- Spec 017: Multi-Currency Support
- Spec 019: Notifications

### External Dependencies

- Python standard library only (`decimal`, `datetime`, `uuid`, `enum`)
- No third-party libraries required for core types
- Calendar-accurate date arithmetic (e.g., `dateutil.relativedelta`) may be used for `RetentionPeriod.expiration_from()` — this is an implementation choice

---

## 9. Constraints

- **Pure Python** — zero framework dependencies in the domain layer
- **No floating-point** — all monetary amounts use `Decimal`
- **UTC only** — all timestamps are UTC with timezone awareness
- **Immutable value objects** — value objects cannot be modified after construction
- **Identity equality for entities** — entities are equal by ID, not by attributes
- **Static currency enum** — adding currencies requires a code change; no runtime admin management of currencies in the shared kernel

---

## 10. Open Questions

None — all questions have been resolved during the clarification phase.

---

## 11. Appendix

### Glossary

| Term | Definition |
|------|------------|
| **Value Object** | A domain concept defined entirely by its attributes. Immutable, no identity. Two instances with the same attributes are equal. |
| **Entity** | A domain concept with a unique identity that persists and changes over time. Equal by identity, not by attributes. |
| **Aggregate Root** | An entity that serves as the consistency boundary for a group of related entities and value objects. All external access goes through the root. |
| **Domain Event** | An immutable record of something meaningful that happened in the domain. Named in past tense. |
| **Shared Kernel** | A small, carefully curated set of domain types shared across multiple bounded contexts. Changes require agreement from all consuming contexts. |
| **Soft Delete** | Marking an entity as deleted without removing it from storage, allowing recovery within a retention window. |
| **Hard Delete** | Permanent, irrecoverable removal of an entity from storage. |
| **Retention Period** | The duration a soft-deleted entity is kept before automatic hard deletion. |
| **Banker's Rounding** | Rounding mode (ROUND_HALF_EVEN) where .5 rounds to the nearest even number. Industry standard for financial calculations to avoid systematic bias. |
| **Anti-Corruption Layer (ACL)** | A translation boundary between bounded contexts that prevents one context's model from leaking into another. |

### References

- [Functional Requirements Document](../../docs/functional-requirements.md)
- [Specification Index](../README.md)
- ISO 4217 — Currency codes standard
- Python `decimal` module — Arbitrary precision decimal arithmetic

---

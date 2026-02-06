# Spec 001: Shared Kernel

**Status:** Draft
**Bounded Context:** Shared (used by all contexts)
**Dependencies:** None
**Blocks:** 002, 006, 007, 013, 016, 017, 019

---

## 1. Overview

The Shared Kernel provides the foundational building blocks used across all bounded contexts in the Emerald Finance Platform. It contains base entity traits, common value objects, and the domain event infrastructure. These are the lowest-level abstractions that every other context depends on.

**Key Principle:** The shared kernel is intentionally small. Only concepts that are truly shared across multiple bounded contexts belong here. Context-specific value objects (e.g., `PermissionLevel`, `AccountName`) belong in their respective contexts.

## 2. Scope

### In Scope

- Base entity traits (identity, timestamps, audit fields, soft delete support)
- Common value objects: `Money`, `Currency`, `DateRange`, `RetentionPeriod`
- Domain event base infrastructure
- Domain exception base types

### Out of Scope

- Context-specific value objects (e.g., `EmailAddress`, `IBAN`, `TaxonomyPath`)
- Repository interfaces (each context defines its own)
- Application layer concerns (use cases, command/query handlers)

## 3. Value Objects

### 3.1 Money

Represents a monetary amount with its currency. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| amount | Decimal | The monetary amount (arbitrary precision) |
| currency | Currency | The currency of this money |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__add__(other: Money) -> Money` | Add two Money values | `CurrencyMismatchError` if currencies differ |
| `__sub__(other: Money) -> Money` | Subtract two Money values | `CurrencyMismatchError` if currencies differ |
| `__neg__() -> Money` | Negate the amount | - |
| `__eq__(other: Money) -> bool` | Equality comparison (amount and currency) | - |
| `__lt__(other: Money) -> bool` | Less-than comparison | `CurrencyMismatchError` if currencies differ |
| `is_zero() -> bool` | Whether amount is zero | - |
| `is_positive() -> bool` | Whether amount is greater than zero | - |
| `is_negative() -> bool` | Whether amount is less than zero | - |
| `round_to_currency() -> Money` | Round to currency's decimal places | - |

**Business Rules:**

- Addition and subtraction only allowed between same-currency values
- Comparison only allowed between same-currency values
- Amount uses arbitrary precision decimal (not floating point)
- Rounding follows currency's `decimal_places` (e.g., 2 for USD, 0 for JPY)

**Construction:**

```
Money(amount=Decimal("100.50"), currency=Currency.USD)
Money.zero(currency=Currency.EUR)  # convenience constructor
```

### 3.2 Currency

Represents an ISO 4217 currency. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| code | str | ISO 4217 code (e.g., "USD", "EUR") |
| symbol | str | Display symbol (e.g., "$", "EUR") |
| name | str | Full name (e.g., "US Dollar") |
| decimal_places | int | Number of decimal places (e.g., 2 for USD, 0 for JPY) |

**Behavior:**

| Method | Description |
|--------|-------------|
| `__eq__(other: Currency) -> bool` | Equality by code |
| `__hash__() -> int` | Hashable by code |

**Business Rules:**

- Code must be a valid 3-letter ISO 4217 code
- Currency instances are typically loaded from master data (admin-managed)
- Core set of currencies provided as constants (USD, EUR, GBP, JPY, etc.)

### 3.3 DateRange

Represents a time period between two dates. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| start_date | date | Start of range (inclusive) |
| end_date | date | End of range (inclusive) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `contains(d: date) -> bool` | Whether date falls within range | - |
| `overlaps(other: DateRange) -> bool` | Whether ranges overlap | - |
| `duration_days() -> int` | Number of days in range | - |

**Business Rules:**

- `start_date` must be less than or equal to `end_date`
- Both dates are inclusive

### 3.4 RetentionPeriod

Represents a duration for data retention policies. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| duration | int | Numeric duration value |
| unit | RetentionUnit | DAYS, MONTHS, or YEARS |

**Behavior:**

| Method | Description |
|--------|-------------|
| `expiration_from(start: datetime) -> datetime` | Calculate when retention expires |
| `to_days() -> int` | Approximate total days |
| `__eq__` / `__lt__` / `__gt__` | Comparison by total duration |

**Enum - RetentionUnit:**

| Value | Description |
|-------|-------------|
| DAYS | Duration in days |
| MONTHS | Duration in calendar months |
| YEARS | Duration in calendar years |

## 4. Base Entity Traits

### 4.1 Entity Identity

All entities have a UUID-based identity assigned at creation.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique identifier, assigned at creation |

**Rules:**

- IDs are UUIDs (v4 or v7, implementation choice)
- IDs are assigned at entity creation time (not by the database)
- IDs are immutable once assigned

### 4.2 Timestamped Entity

All entities track creation and modification times.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| created_at | datetime | No | When the entity was created (UTC) |
| updated_at | datetime | Auto | When the entity was last modified (UTC) |

**Rules:**

- `created_at` is set once at entity creation and never changes
- `updated_at` is automatically set on every state change
- All timestamps are in UTC

### 4.3 Soft-Deletable Entity

Entities that support soft deletion extend this trait.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| deleted_at | datetime? | Yes | When soft delete occurred (None = active) |
| deleted_by | UUID? | Yes | Who performed the deletion |
| deletion_reason | str? | Yes | Optional reason for deletion |
| hard_delete_scheduled_at | datetime? | Yes | When automatic hard delete will occur |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `soft_delete(deleted_by: UUID, reason: str?, retention: RetentionPeriod) -> None` | Mark as soft deleted | `AlreadyDeletedError` if already deleted |
| `recover() -> None` | Restore from soft delete | `NotDeletedError` if not deleted |
| `is_deleted() -> bool` | Whether entity is soft deleted | - |
| `is_active() -> bool` | Whether entity is active (not deleted) | - |

**Rules:**

- Setting `deleted_at` marks the entity as soft deleted
- `hard_delete_scheduled_at` is calculated from `deleted_at` + retention period
- `recover()` clears `deleted_at`, `deleted_by`, `deletion_reason`, and `hard_delete_scheduled_at`
- Cannot recover if parent entity is deleted (enforced by aggregate, not this trait)

### 4.4 Auditable Entity

Entities that track who created/modified them.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| created_by | UUID | No | Who created this entity |
| updated_by | UUID | Auto | Who last modified this entity |

## 5. Domain Event Infrastructure

### 5.1 Base Domain Event

All domain events extend this base.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| event_id | UUID | Unique event identifier |
| occurred_at | datetime | When the event occurred (UTC) |
| aggregate_id | UUID | ID of the aggregate that produced the event |
| aggregate_type | str | Type name of the aggregate |

**Design Principles:**

- Domain events are immutable records of something that happened
- Events are named in past tense (e.g., `AccountCreated`, `TransactionSplit`)
- Events are raised by aggregates, collected, and dispatched after persistence
- Events carry only the data needed by consumers (no full entity dumps)

### 5.2 Event Collection

Aggregates collect domain events internally and expose them for dispatch.

**Pattern:**

```
Aggregate:
  _events: list[DomainEvent]  (private, not persisted)

  + collect_events() -> list[DomainEvent]
      Returns accumulated events and clears the internal list.
      Called by the application layer after successful persistence.
```

## 6. Domain Exception Base Types

### 6.1 Exception Hierarchy

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

**Rules:**

- All domain exceptions inherit from `DomainError`
- Domain exceptions carry a machine-readable `code` and human-readable `message`
- Domain exceptions are raised in the domain layer, translated to HTTP responses in the presentation layer

## 7. Acceptance Criteria

### Value Objects

- [ ] `Money` supports addition, subtraction, comparison, and negation for same-currency values
- [ ] `Money` raises `CurrencyMismatchError` for cross-currency arithmetic
- [ ] `Money` uses `Decimal` for arbitrary-precision amounts (no float)
- [ ] `Currency` validates ISO 4217 codes
- [ ] `DateRange` validates `start_date <= end_date`
- [ ] `DateRange.contains()` and `DateRange.overlaps()` work correctly
- [ ] `RetentionPeriod` correctly calculates expiration dates including month/year boundaries

### Base Entity Traits

- [ ] Entity IDs are UUIDs generated at creation time
- [ ] `created_at` is immutable after construction
- [ ] `updated_at` changes on every state modification
- [ ] `soft_delete()` sets `deleted_at`, `deleted_by`, and `hard_delete_scheduled_at`
- [ ] `recover()` clears all deletion-related fields
- [ ] `soft_delete()` raises `AlreadyDeletedError` if called on a deleted entity
- [ ] `recover()` raises `NotDeletedError` if called on an active entity

### Domain Events

- [ ] Aggregates can collect and expose domain events
- [ ] `collect_events()` returns events and clears the internal list
- [ ] Domain events are immutable after creation
- [ ] Domain events carry `event_id`, `occurred_at`, `aggregate_id`, `aggregate_type`

### Domain Exceptions

- [ ] All domain exceptions extend `DomainError`
- [ ] Exceptions carry `code` (machine-readable) and `message` (human-readable)
- [ ] Exception hierarchy matches the defined tree

## 8. Technical Notes

- All value objects must be immutable (frozen dataclass or equivalent)
- Value objects must implement `__eq__` and `__hash__` for use in sets and as dict keys
- Base entity traits should use mixins or composition (not deep inheritance hierarchies)
- All timestamps are UTC with timezone awareness (`datetime` with `tzinfo`)
- The domain layer has zero framework dependencies (pure Python)

# Spec-001: Shared Kernel — Changelog

## v1.0.0 — 2026-02-05

**Status:** Implemented

### Summary

Implemented the foundational Shared Kernel for the Emerald Finance Platform — the innermost domain layer that all bounded contexts depend on. Pure Python with zero framework dependencies.

### What Was Built

**Exception Hierarchy (11 types)**
- `DomainError` base with `code` and `message` attributes
- `ValidationError` > `InvalidValueError`, `InvariantViolationError`
- `ConflictError` > `AlreadyExistsError`, `AlreadyDeletedError`
- `NotFoundError`, `NotDeletedError`, `AuthorizationError`, `CurrencyMismatchError`

**Value Objects (4 types)**
- `Currency` — ISO 4217 enum with 10 currencies (USD, EUR, GBP, JPY, CHF, CAD, AUD, MXN, BRL, CNY)
- `Money` — Decimal-only arithmetic, Banker's rounding, cross-currency protection
- `DateRange` — Inclusive start/end with `contains()`, `overlaps()`, `duration_days()`
- `RetentionPeriod` — Calendar-accurate expiration via `dateutil.relativedelta`

**Entity Traits (4 mixins)**
- `Entity` — UUID identity, identity-based equality and hashing
- `TimestampedMixin` — `created_at` (immutable) + `updated_at` with `_touch()`
- `SoftDeletableMixin` — `soft_delete()` / `recover()` lifecycle with retention scheduling
- `AuditableMixin` — `created_by` (immutable) + `updated_by` actor tracking

**Aggregate Root**
- `AggregateRoot` — Combines Entity + TimestampedMixin + domain event collection
- `_register_event()` / `collect_events()` pattern for deferred event dispatch

**Domain Events**
- `DomainEvent` — Frozen dataclass base with `event_id`, `occurred_at`, `aggregate_id`, `aggregate_type`

### Test Coverage

- 160 unit tests, all passing
- Tests cover: construction, validation, arithmetic, edge cases, equality, hashability, immutability, error paths

### Quality Checks

- `uv run pytest` — 160 passed
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run ty check` — clean

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Value object immutability | `@dataclass(frozen=True)` | Built-in equality, hashing, immutability |
| Currency implementation | Python `Enum` | Static set, singleton members, iteration support |
| Entity traits | Mixin classes with cooperative `super().__init__()` | Composable via multiple inheritance |
| Calendar date math | `python-dateutil` (`relativedelta`) | Battle-tested month/year boundary handling |
| Mixin kwargs typing | `**kwargs: Any` | Required by `ty` for MRO forwarding of typed keyword args |

### Files Created

```
src/emerald/shared_kernel/
  __init__.py                      # Public API (22 exported types)
  exceptions/
    __init__.py
    base.py                        # 11 exception types
  value_objects/
    __init__.py
    currency.py                    # Currency enum (10 currencies)
    money.py                       # Money value object
    date_range.py                  # DateRange value object
    retention_period.py            # RetentionUnit enum + RetentionPeriod
  entities/
    __init__.py
    entity.py                      # Entity base (identity trait)
    timestamped.py                 # TimestampedMixin
    soft_deletable.py              # SoftDeletableMixin
    auditable.py                   # AuditableMixin
    aggregate_root.py              # AggregateRoot base
  events/
    __init__.py
    domain_event.py                # DomainEvent base

tests/unit/shared_kernel/
  exceptions/test_exceptions.py    # 33 tests
  value_objects/
    test_currency.py               # 14 tests
    test_money.py                  # 29 tests
    test_date_range.py             # 14 tests
    test_retention_period.py       # 16 tests
  entities/
    test_entity.py                 # 8 tests
    test_timestamped.py            # 8 tests
    test_soft_deletable.py         # 8 tests
    test_auditable.py              # 5 tests
    test_aggregate_root.py         # 9 tests
  events/
    test_domain_event.py           # 6 tests
```

### Dependencies

- `python-dateutil>=2.9.0` (runtime — calendar-accurate date arithmetic)
- `pytest>=8.0` (dev)
- `ruff>=0.9.0` (dev)
- `ty>=0.0.15` (dev)

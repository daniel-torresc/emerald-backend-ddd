# Spec 035 — Domain Model Consistency & Hygiene

**Status:** DRAFT
**Priority:** P2/P3 (cleanup, no blocking dependencies)
**Dependencies:** spec-001 through spec-015 (all implemented domain specs)
**Blocked by:** None
**Blocks:** None (but should be done before infrastructure to avoid propagating inconsistencies)

---

## 1. Problem Statement

A codebase review across all 15 implemented domain specs revealed several consistency issues, minor design debts, and convention violations that should be resolved before the infrastructure layer solidifies these patterns into ORM mappings, API contracts, and database schemas.

None of these are critical bugs — the test suite passes with 2600+ tests. But each inconsistency creates a small tax on future development and makes the codebase harder to reason about.

---

## 2. Issues Catalog

### 2.1 Version Initialization Inconsistency

**Severity:** Medium
**Impact:** Optimistic concurrency in ORM layer

`AggregateRoot.__init__` defaults `version=0`. But factory methods disagree:

| Aggregate | Factory Method | Version Set |
|-----------|---------------|-------------|
| `User` | `register()` | Not set (defaults to 0) |
| `User` | `register_via_social()` | Not set (defaults to 0) |
| `User` | `provision_as_superadmin()` | Not set (defaults to 0) |
| `Account` | `create()` | Explicitly `version=1` |
| `Taxonomy` | `create()` | Explicitly `version=1` |
| `Transaction` | `create()` | Not set (defaults to 0) |
| `BankConnection` | `create()` | Not set (defaults to 0) |

**Fix:** Standardize all factories to explicitly set `version=1`. A newly created aggregate is at version 1 (its first persisted state). Version 0 should be reserved for "not yet created" (which is never a valid persisted state).

**Files to change:**
- `src/emerald/iam/domain/models/aggregates/user.py` — all 3 factory methods
- `src/emerald/core_finance/domain/models/aggregates/transaction.py` — `create()`
- `src/emerald/integrations/domain/models/aggregates/bank_connection.py` — `create()`

---

### 2.2 Embedded Constants

**Severity:** Low
**Impact:** ORM column sizing, maintainability

Several domain constants are defined as class-level attributes inside aggregate files instead of in `{context}/domain/constants.py`:

| Constant | Current Location | Should Move To |
|----------|-----------------|---------------|
| `User._MAX_PASSWORD_HISTORY = 5` | `iam/domain/models/aggregates/user.py` | `iam/domain/constants.py` as `MAX_PASSWORD_HISTORY` |
| `Account._MAX_NOTES_LENGTH = 500` | `core_finance/domain/models/aggregates/account.py` | `core_finance/domain/constants.py` as `MAX_ACCOUNT_NOTES_LENGTH` |

**Fix:** Move to constants files, update references in aggregate classes.

---

### 2.3 Missing Domain Events

**Severity:** Medium
**Impact:** Audit logging (spec-016), event completeness

The following state-changing methods modify aggregate state and call `_touch()` but do not register domain events:

| Aggregate | Method | State Changed | Event Missing |
|-----------|--------|--------------|---------------|
| `User` | `update_full_name()` | `full_name` field | `UserFullNameUpdated` |
| `User` | `update_preferences()` | `preferences` field | `UserPreferencesUpdated` |
| `Transaction` | `mark_for_review()` | `review_status` -> `TO_REVIEW` | `TransactionMarkedForReview` |

Compare with `User.update_email()` which correctly emits `UserEmailChanged`, and `Transaction.mark_as_reviewed()` which correctly emits `TransactionReviewed`. The pattern violation is clear.

**Fix:** Add 3 new frozen dataclass events and register them in the respective methods.

**New events:**
```python
@dataclass(frozen=True)
class UserFullNameUpdated(DomainEvent):
    aggregate_type: ClassVar[str] = "User"
    old_name: str | None
    new_name: str | None

@dataclass(frozen=True)
class UserPreferencesUpdated(DomainEvent):
    aggregate_type: ClassVar[str] = "User"

@dataclass(frozen=True)
class TransactionMarkedForReview(DomainEvent):
    aggregate_type: ClassVar[str] = "Transaction"
    account_id: uuid.UUID
    updated_by: uuid.UUID
```

---

### 2.4 Duplicate Constants Across Contexts

**Severity:** Low
**Impact:** Potential drift between contexts

`MAX_MERCHANT_LENGTH` is defined in both contexts with the same value:

- `core_finance/domain/constants.py`: `MAX_MERCHANT_LENGTH: int = 200`
- `integrations/domain/constants.py`: `MAX_MERCHANT_LENGTH: int = 200`

**Fix:** Keep both. Each bounded context owns its own constants — this is correct DDD practice. The values happen to be the same today, but each context should be free to evolve independently. **Add a code comment in the integrations constant** noting the alignment:

```python
# Matches core_finance MAX_MERCHANT_LENGTH by convention (not by import).
MAX_MERCHANT_LENGTH: int = 200
```

---

### 2.5 Mutable Value Objects

**Severity:** Low
**Impact:** Domain purity

Two value-object-like dataclasses are not frozen:

| Class | File | Current | Should Be |
|-------|------|---------|-----------|
| `ProviderCredentials` | `integrations/domain/models/value_objects/provider_credentials.py` | `@dataclass` | `@dataclass(frozen=True)` |
| `UserPreferences` | `iam/domain/models/value_objects/user_preferences.py` | `@dataclass` | `@dataclass(frozen=True)` |

**Convention from CLAUDE.md:** "Value objects: `@dataclass(frozen=True)` with validation in `__post_init__`"

**Fix:** Add `frozen=True`. If any code mutates these objects in-place, refactor to create new instances instead (standard VO replacement pattern).

---

### 2.6 Factory Method Inconsistency in Entities

**Severity:** Low
**Impact:** API consistency

Some entities have `create()` factory methods, others use bare `__init__`:

| Entity | Has `create()` | Notes |
|--------|---------------|-------|
| `Card` | Yes | |
| `Transaction` | Yes | |
| `TransactionTermAssignment` | Yes | |
| `PendingTransaction` | Yes | |
| `SyncHistory` | Yes | |
| `UserRetentionPreference` | Yes | |
| `RefreshToken` | **No** | Uses `__init__` directly in AuthenticationService |
| `PasswordResetToken` | **No** | Uses `__init__` directly in AuthenticationService |
| `AccountShare` | **No** | Created inside Account.share_with() |

**Fix:** No change for `AccountShare` (it's a child entity created by its parent aggregate — correct pattern). For `RefreshToken` and `PasswordResetToken`, add `create()` class methods that encapsulate default creation logic (e.g., auto-generating `id`, setting `created_at` to `now()`). This also makes them consistent with TimestampedMixin entities.

---

### 2.7 Card Missing AuditableMixin

**Severity:** Low
**Impact:** Cannot track "who changed" a card at entity level

`Card` uses `SoftDeletableMixin + TimestampedMixin + Entity` but not `AuditableMixin`:

```python
class Card(SoftDeletableMixin, TimestampedMixin, Entity):
```

This means `Card.update_name()`, `update_network()`, etc. track **when** (`updated_at`) but not **who** (`updated_by`). Changes are audited at the Account level via `CardUpdated` events (which include the actor), so the information exists — but not on the Card entity itself.

**Fix:** Add `AuditableMixin` to Card. This requires:
1. Changing the class declaration to `Card(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity)`
2. Adding `updated_by: uuid.UUID` parameter to all `Card.update_*()` methods
3. Calling `self._set_updated_by(updated_by)` in each update method
4. Updating `Account.update_card_*()` methods to pass `updated_by` through
5. Updating `CardManagementService` to pass `requesting_user_id` through to Card methods
6. Updating `Card.create()` factory to accept `created_by`

**Alternative:** Document the current design as intentional (Card audit tracked via Account events only). This is the lower-effort option if the event-based audit trail is sufficient.

---

### 2.8 Exception Error Code Catalog

**Severity:** Low
**Impact:** API error responses (spec-027)

Many exceptions use generic default codes (`"INVALID_VALUE"`, `"INVARIANT_VIOLATION"`) instead of specific codes. When the API layer maps exceptions to HTTP responses (spec-027), it needs unique codes for client-side error handling.

**Fix:** Audit all custom exceptions and ensure each has a unique, descriptive `code`. Create a reference document (not code — just documentation) listing all error codes for API consumers.

**Example codes that should be explicit:**
```
ACCOUNT_NAME_ALREADY_EXISTS
INSUFFICIENT_PERMISSION
TRANSACTION_ALREADY_SPLIT
CANNOT_SPLIT_CHILD
TAXONOMY_NAME_ALREADY_EXISTS
CIRCULAR_REFERENCE
```

---

### 2.9 Token Entities Missing TimestampedMixin

**Severity:** Low
**Impact:** Pattern consistency

`RefreshToken` and `PasswordResetToken` manually manage `created_at` instead of inheriting from `TimestampedMixin`:

```python
# RefreshToken.__init__
self.created_at = created_at if created_at is not None else datetime.now(UTC)
```

vs. the standard pattern in TimestampedMixin:

```python
# TimestampedMixin.__init__
self._created_at = created_at if created_at is not None else datetime.now(UTC)
```

**Fix:** Refactor both token entities to use `TimestampedMixin`. This gives them the standard `created_at` property (read-only via `@property`) and `updated_at` tracking. Note: these entities don't have an "updated" concept (tokens are created, then either revoked/used or expire), so `updated_at` would just mirror `revoked_at`/`used_at`. Consider whether `TimestampedMixin` is actually appropriate, or whether the current manual approach is intentionally lightweight.

**Recommendation:** Keep as-is. Token entities are intentionally lightweight — they don't need `updated_at` tracking. The manual `created_at` handling is correct for their use case. **Document this as an intentional exception** with a code comment.

---

## 3. Implementation Order

| # | Issue | Effort | Risk |
|---|-------|--------|------|
| 1 | Version initialization (2.1) | 30 min | None |
| 2 | Embedded constants (2.2) | 15 min | None |
| 3 | Missing events (2.3) | 1 hr | Low (new events + tests) |
| 4 | Mutable VOs (2.5) | 15 min | Low (may require refactoring mutations) |
| 5 | Factory methods (2.6) | 30 min | None |
| 6 | Card AuditableMixin (2.7) | 2 hr | Medium (touches Card, Account, Service, tests) |
| 7 | Error code catalog (2.8) | 1 hr | None |
| 8 | Documentation comments (2.4, 2.9) | 15 min | None |

**Total estimated effort:** ~6 hours

---

## 4. Acceptance Criteria

1. All aggregate factories set `version=1` explicitly
2. `_MAX_PASSWORD_HISTORY` and `_MAX_NOTES_LENGTH` moved to respective `constants.py` files
3. `User.update_full_name()` emits `UserFullNameUpdated` event
4. `User.update_preferences()` emits `UserPreferencesUpdated` event
5. `Transaction.mark_for_review()` emits `TransactionMarkedForReview` event
6. `ProviderCredentials` and `UserPreferences` are `@dataclass(frozen=True)`
7. `RefreshToken` and `PasswordResetToken` have `create()` factory methods
8. Card either gains `AuditableMixin` or has documented rationale for omitting it
9. All custom exceptions have unique, descriptive error codes
10. All existing tests pass (2600+)
11. New tests cover added events and factory methods
12. All quality checks pass (`ruff check`, `ruff format`, `ty check`)

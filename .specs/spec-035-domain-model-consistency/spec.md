# Spec 035 — Domain Model Consistency & Hygiene

**Version:** 1.0
**Status:** Draft
**Date:** 2026-02-19
**Dependencies:** spec-001 through spec-015 (all implemented domain specs), spec-032 (async ports)
**Blocked by:** None
**Blocks:** None (should complete before infrastructure layer solidifies patterns)

---

## 1. Overview

A codebase review across all 15 implemented domain specs revealed consistency issues and minor design debts that should be resolved before the infrastructure layer solidifies these patterns into ORM mappings, API contracts, and database schemas. None are critical bugs — the test suite passes with 2600+ tests — but each inconsistency creates a small tax on future development.

---

## 2. Background & Context

### Problem Statement

Incremental spec-by-spec development naturally introduces minor inconsistencies as conventions evolve. Patterns established in later specs (e.g., Account setting `version=1`, Transaction using AuditableMixin) were not backported to earlier entities. These inconsistencies would propagate into the infrastructure layer if not resolved now.

### Business Goals

- Uniform domain model conventions across all bounded contexts
- Clean foundation for ORM mappings (spec-022 through spec-025)
- Consistent audit trail at entity level for all mutable entities

---

## 3. Scope

### In Scope

- Version initialization standardization across all aggregate factories
- Extracting embedded constants to context-level constants files
- Adding missing domain events to state-changing methods
- Adding AuditableMixin to Card entity with full updated_by flow
- Adding `create()` factory methods to RefreshToken and PasswordResetToken
- Documentation comments for intentional design exceptions
- Correcting the duplicate-constants alignment comment

### Out of Scope

- Token entities (RefreshToken, PasswordResetToken) adopting TimestampedMixin — intentionally lightweight
- Changes to exception error codes — verified all concrete exceptions already have unique codes
- Changes to value object frozen status — verified ProviderCredentials and UserPreferences are already `frozen=True`
- Any infrastructure or persistence layer changes
- New application services or commands (beyond what's needed for the fixes above)

---

## 4. Requirements

### 4.1 Version Initialization Standardization

**Priority:** Must Have

All aggregate factory methods must explicitly set `version=1`. A newly created aggregate is at version 1 (its first persisted state). Version 0 is reserved for "not yet created."

**Current state:**

| Aggregate | Factory Method | Current |
|-----------|---------------|---------|
| `User` | `register()` | Not set (defaults to 0) |
| `User` | `register_via_social()` | Not set (defaults to 0) |
| `User` | `provision_as_superadmin()` | Not set (defaults to 0) |
| `Transaction` | `create()` | Not set (defaults to 0) |
| `Account` | `create()` | Already `version=1` |
| `Taxonomy` | `create()` | Already `version=1` |
| `BankConnection` | `create()` | Already `version=1` |

**Files to change:**
- `src/emerald/iam/domain/models/aggregates/user.py` — all 3 factory methods
- `src/emerald/core_finance/domain/models/aggregates/transaction.py` — `create()`

**Acceptance Criteria:**
- [ ] All 4 factory methods pass `version=1` in their constructor call
- [ ] Existing tests updated to expect `version=1` on newly created aggregates
- [ ] No test regressions

---

### 4.2 Embedded Constants Extraction

**Priority:** Should Have

Move domain constants from aggregate files to their respective `{context}/domain/constants.py` files.

| Constant | Current Location | Target Location | Public Name |
|----------|-----------------|----------------|-------------|
| `_MAX_PASSWORD_HISTORY = 5` | `iam/domain/models/aggregates/user.py` (module-level) | `iam/domain/constants.py` | `MAX_PASSWORD_HISTORY` |
| `_MAX_NOTES_LENGTH = 500` | `core_finance/domain/models/aggregates/account.py` (module-level) | `core_finance/domain/constants.py` | `MAX_ACCOUNT_NOTES_LENGTH` |

**Acceptance Criteria:**
- [ ] Constants moved to respective `constants.py` files with public names
- [ ] Aggregate files import from `constants.py` instead of defining locally
- [ ] Constants re-exported in context `__init__.py` if part of public API
- [ ] No test regressions

---

### 4.3 Missing Domain Events

**Priority:** Must Have

Three state-changing methods modify aggregate state and call `_touch()` but do not register domain events. This violates the established pattern (compare `User.update_email()` which emits `UserEmailChanged`, and `Transaction.mark_as_reviewed()` which emits `TransactionReviewed`).

#### 4.3.1 UserFullNameUpdated

**Method:** `User.update_full_name()`
**Event definition:**
```python
@dataclass(frozen=True)
class UserFullNameUpdated(DomainEvent):
    aggregate_type: ClassVar[str] = "User"
    old_name: str | None
    new_name: str | None
```

#### 4.3.2 UserPreferencesUpdated

**Method:** `User.update_preferences()`
**Event definition (lightweight — no payload beyond aggregate_id):**
```python
@dataclass(frozen=True)
class UserPreferencesUpdated(DomainEvent):
    aggregate_type: ClassVar[str] = "User"
```

#### 4.3.3 TransactionMarkedForReview

**Method:** `Transaction.mark_for_review()`
**Event definition:**
```python
@dataclass(frozen=True)
class TransactionMarkedForReview(DomainEvent):
    aggregate_type: ClassVar[str] = "Transaction"
    account_id: uuid.UUID
    updated_by: uuid.UUID
```

**Acceptance Criteria:**
- [ ] All 3 events defined as frozen dataclasses extending `DomainEvent`
- [ ] Each method registers its event via `_register_event()` after state change
- [ ] Events added to respective context `__init__.py` exports
- [ ] Unit tests verify event emission (event type, payload fields)
- [ ] Idempotent methods (mark_for_review when already TO_REVIEW) do NOT emit events

---

### 4.4 Duplicate Constants Alignment Comment

**Priority:** Could Have

`MAX_MERCHANT_LENGTH = 200` is intentionally defined in both `core_finance/domain/constants.py` and `integrations/domain/constants.py`. This is correct DDD practice — each bounded context owns its own constants.

**Fix:** Add an alignment comment in the integrations constant:

```python
# Aligned with core_finance MAX_MERCHANT_LENGTH by convention (not by import).
MAX_MERCHANT_LENGTH: int = 200
```

**Acceptance Criteria:**
- [ ] Comment added to `integrations/domain/constants.py`

---

### 4.5 Factory Methods for Token Entities

**Priority:** Should Have

`RefreshToken` and `PasswordResetToken` use `__init__` directly in `AuthenticationService`, while all other entities use `create()` factory methods.

**Fix:** Add `create()` classmethods to both entities that encapsulate default creation logic (auto-generating `id`, setting `created_at` to `now(UTC)`).

**RefreshToken.create() signature:**
```python
@classmethod
def create(
    cls,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    device_info: str | None = None,
) -> RefreshToken:
```

**PasswordResetToken.create() signature:**
```python
@classmethod
def create(
    cls,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> PasswordResetToken:
```

**Acceptance Criteria:**
- [ ] Both entities have `create()` classmethods
- [ ] `AuthenticationService` updated to use `create()` instead of direct `__init__`
- [ ] Factory methods auto-generate `id` via `uuid.uuid4()` and `created_at` via `datetime.now(UTC)`
- [ ] No test regressions

---

### 4.6 Card AuditableMixin Addition

**Priority:** Must Have

`Card` uses `SoftDeletableMixin + TimestampedMixin + Entity` but lacks `AuditableMixin`. This means card updates track **when** (`updated_at`) but not **who** (`updated_by`). For consistency with `Transaction` (which has AuditableMixin) and to support entity-level audit trails, Card should gain AuditableMixin.

#### 4.6.1 Card Entity Changes

**Class declaration change:**
```python
class Card(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity):
```

**Constructor:** Add `created_by: uuid.UUID` parameter (required by AuditableMixin).

**Factory method:** `Card.create()` must accept `created_by: uuid.UUID` parameter and pass it through.

**Update methods:** All 6 update methods gain an `updated_by: uuid.UUID` parameter and call `self._set_updated_by(updated_by)`:
- `update_name(card_name: str, updated_by: uuid.UUID) -> None`
- `update_network(card_network: CardNetwork | None, updated_by: uuid.UUID) -> None`
- `update_expiry(month: int, year: int, updated_by: uuid.UUID) -> None`
- `update_credit_limit(credit_limit: Money | None, updated_by: uuid.UUID) -> None`
- `update_issuing_institution(institution: str | None, updated_by: uuid.UUID) -> None`
- `update_notes(notes: str | None, updated_by: uuid.UUID) -> None`

**Soft-delete:** `Card` inherits `SoftDeletableMixin.soft_delete()` which already accepts `deleted_by` — no change needed.

#### 4.6.2 Account Aggregate Changes

All card-related methods on `Account` that delegate to `Card.update_*()` must accept and forward `updated_by`:

- `add_card(card: Card) -> None` — no change (card already created with `created_by`)
- `update_card_name(card_id, name, updated_by) -> None`
- `update_card_network(card_id, network, updated_by) -> None`
- `update_card_expiry(card_id, month, year, updated_by) -> None`
- `update_card_credit_limit(card_id, credit_limit, updated_by) -> None`
- `update_card_issuing_institution(card_id, institution, updated_by) -> None`
- `update_card_notes(card_id, notes, updated_by) -> None`

Each method forwards `updated_by` to the corresponding `card.update_*()` call.

#### 4.6.3 CardManagementService Changes

The service already has `cmd.requesting_user_id` available. Changes:

- `add_card()`: Pass `created_by=cmd.requesting_user_id` to `Card.create()`
- All `update_card_*()` methods: Pass `updated_by=cmd.requesting_user_id` to `account.update_card_*()`

#### 4.6.4 Test Updates

- Card unit tests: All card construction must pass `created_by`
- Card update tests: All update calls must pass `updated_by`, verify `card.updated_by` is set
- Account card tests: Forward `updated_by` in all card update calls
- Service tests: Verify `requesting_user_id` flows through to card entity

**Acceptance Criteria:**
- [ ] Card inherits from `SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity`
- [ ] `Card.create()` accepts `created_by` parameter
- [ ] All 6 `Card.update_*()` methods accept `updated_by` and call `_set_updated_by()`
- [ ] All 6 `Account.update_card_*()` methods accept and forward `updated_by`
- [ ] `CardManagementService` passes `requesting_user_id` as `created_by`/`updated_by`
- [ ] All existing card tests updated for new signatures
- [ ] New tests verify `updated_by` is correctly set on card after updates

---

### 4.7 Documentation Comments

**Priority:** Could Have

Add code comments documenting intentional design exceptions:

1. **Token entities (RefreshToken, PasswordResetToken):** Comment explaining they intentionally do NOT use `TimestampedMixin` because they are lightweight entities that don't need `updated_at` tracking — they are created, then either revoked/used or expire.

2. **AccountShare:** Comment confirming it intentionally lacks a `create()` factory method because it is a child entity created exclusively by its parent aggregate (`Account.share_with()`).

**Acceptance Criteria:**
- [ ] Comments added to RefreshToken and PasswordResetToken class docstrings
- [ ] Comment added to AccountShare class docstring

---

## 5. Implementation Order

| # | Requirement | Effort | Risk | Dependencies |
|---|------------|--------|------|-------------|
| 1 | Version initialization (4.1) | 20 min | None | — |
| 2 | Embedded constants (4.2) | 15 min | None | — |
| 3 | Missing events (4.3) | 45 min | Low | — |
| 4 | Token factory methods (4.5) | 30 min | None | — |
| 5 | Card AuditableMixin (4.6) | 2 hr | Medium | — |
| 6 | Documentation comments (4.4, 4.7) | 10 min | None | — |

Items 1–4 and 6 are independent of each other and can be implemented in any order. Item 5 (Card AuditableMixin) is the most involved and should be done last to minimize merge conflicts.

**Total estimated effort:** ~4 hours

---

## 6. Quality Gates

All of the following must pass after implementation:

1. `uv run pytest` — all 2600+ tests pass (plus new tests)
2. `uv run ruff check .` — no lint violations
3. `uv run ruff format --check .` — no formatting issues
4. `uv run ty check` — no type errors
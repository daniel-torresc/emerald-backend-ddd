# Domain Model Consistency & Hygiene — Implementation Plan

**Spec:** `.specs/spec-035-domain-model-consistency/spec.md`
**Version:** 1.0
**Date:** 2026-02-19

---

## 1. Overview

This plan addresses 6 consistency issues across the domain model that accumulated during incremental spec-by-spec development. All changes are domain-layer and application-layer only — no infrastructure changes. The work follows an inside-out approach: domain entities first, then application services, then tests.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| 4.1 Version init | Domain | `User`, `Transaction` factory methods |
| 4.2 Constants extraction | Domain | `iam/domain/constants.py`, `core_finance/domain/constants.py` |
| 4.3 Missing events | Domain | `UserFullNameUpdated`, `UserPreferencesUpdated`, `TransactionMarkedForReview` |
| 4.4 Alignment comment | Domain | `integrations/domain/constants.py` |
| 4.5 Token factories | Domain + Application | `RefreshToken.create()`, `PasswordResetToken.create()`, `AuthenticationService` |
| 4.6 Card AuditableMixin | Domain + Application | `Card`, `Account`, `CardManagementService` |
| 4.7 Documentation comments | Domain | `RefreshToken`, `PasswordResetToken`, `AccountShare` |

### 2.2 Key Design Decisions

**Decision 1: Event base classes** — New IAM events extend `UserEvent` (which has `aggregate_type = "user"`). New transaction event extends `TransactionEvent` (which has `aggregate_type = "transaction"`). This matches existing patterns.

**Decision 2: RefreshToken.create() signature** — The spec signature omits `family_id` and `portal_context`, but these are required for RefreshToken construction (see current code). The factory must include all required fields. We follow the spec's guidance on auto-generating `id` and `created_at`, but keep the full parameter set needed for the entity.

**Decision 3: Card AuditableMixin MRO** — `Card(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity)` — AuditableMixin slots in before TimestampedMixin, matching the Account/Transaction pattern. The `**kwargs: Any` already on Card's `__init__` will handle cooperative MRO.

---

## 3. Implementation Tasks

### Phase 1: Independent Quick Fixes (Tasks 1–4, parallelizable)

#### TASK-001: Version Initialization Standardization
**Layer:** Domain
**Depends On:** None

**Description:**
Add `version=1` to all aggregate factory methods that currently default to version 0.

**Files to Modify:**
- `src/emerald/iam/domain/models/aggregates/user.py` — `register()`, `register_via_social()`, `provision_as_superadmin()`: add `version=1` to the `cls(...)` call
- `src/emerald/core_finance/domain/models/aggregates/transaction.py` — `create()`: add `version=1` to the `cls(...)` call

**Test Updates:**
- `tests/unit/iam/` — any tests asserting `user.version == 0` must change to `== 1`
- `tests/unit/core_finance/` — any tests asserting `transaction.version == 0` must change to `== 1`

**Acceptance Criteria:**
- [ ] All 4 factory methods pass `version=1`
- [ ] All tests pass with updated version expectations

---

#### TASK-002: Embedded Constants Extraction
**Layer:** Domain
**Depends On:** None

**Description:**
Move module-level private constants to their respective `constants.py` files with public names.

**Files to Modify:**
- `src/emerald/iam/domain/constants.py` — add `MAX_PASSWORD_HISTORY: int = 5`
- `src/emerald/iam/domain/models/aggregates/user.py` — remove `_MAX_PASSWORD_HISTORY = 5`, import `MAX_PASSWORD_HISTORY` from constants, update usages
- `src/emerald/core_finance/domain/constants.py` — add `MAX_ACCOUNT_NOTES_LENGTH: int = 500`
- `src/emerald/core_finance/domain/models/aggregates/account.py` — remove `_MAX_NOTES_LENGTH = 500`, import `MAX_ACCOUNT_NOTES_LENGTH` from constants, update usages
- `src/emerald/iam/__init__.py` — re-export `MAX_PASSWORD_HISTORY` if not already present
- `src/emerald/core_finance/__init__.py` — re-export `MAX_ACCOUNT_NOTES_LENGTH` if not already present

**Acceptance Criteria:**
- [ ] Constants defined in `constants.py` with public names
- [ ] Aggregate files import from `constants.py`
- [ ] Constants re-exported in context `__init__.py`
- [ ] No test regressions

---

#### TASK-003: Missing Domain Events
**Layer:** Domain
**Depends On:** None

**Description:**
Add 3 missing domain events to state-changing methods that currently call `_touch()` without emitting events.

**Files to Create/Modify:**
- `src/emerald/iam/domain/events/user_events.py` — add `UserFullNameUpdated` and `UserPreferencesUpdated`
  ```python
  @dataclass(frozen=True)
  class UserFullNameUpdated(UserEvent):
      new_name: str | None

  @dataclass(frozen=True)
  class UserPreferencesUpdated(UserEvent):
      pass  # Lightweight — no payload beyond aggregate_id
  ```
- `src/emerald/iam/domain/models/aggregates/user.py` — `update_full_name()`: register `UserFullNameUpdated` after state change; `update_preferences()`: register `UserPreferencesUpdated` after state change
- `src/emerald/core_finance/domain/events/transaction_events.py` — add `TransactionMarkedForReview`
  ```python
  @dataclass(frozen=True)
  class TransactionMarkedForReview(TransactionEvent):
      account_id: uuid.UUID
      updated_by: uuid.UUID
  ```
- `src/emerald/core_finance/domain/models/aggregates/transaction.py` — `mark_for_review()`: register `TransactionMarkedForReview` after state change (but NOT when idempotent early-return fires)
- `src/emerald/iam/domain/events/__init__.py` — re-export new events
- `src/emerald/iam/__init__.py` — re-export new events
- `src/emerald/core_finance/domain/events/__init__.py` — re-export new event
- `src/emerald/core_finance/__init__.py` — re-export new event

**Test Files to Create/Modify:**
- `tests/unit/iam/domain/aggregates/test_user.py` — add tests for event emission on `update_full_name()` and `update_preferences()`
- `tests/unit/core_finance/domain/aggregates/test_transaction.py` — add test for event emission on `mark_for_review()`, verify idempotent case emits NO event

**Acceptance Criteria:**
- [ ] 3 events defined as frozen dataclasses extending context-specific base events
- [ ] Each method registers its event after state change
- [ ] Events added to all `__init__.py` exports
- [ ] Tests verify event type and payload fields
- [ ] Idempotent `mark_for_review` (already TO_REVIEW) does NOT emit event

---

#### TASK-004: Documentation Comments & Alignment
**Layer:** Domain
**Depends On:** None

**Description:**
Add alignment comment to integrations constants and documentation comments to entities with intentional design exceptions.

**Files to Modify:**
- `src/emerald/integrations/domain/constants.py` — add alignment comment above `MAX_MERCHANT_LENGTH`:
  ```python
  # Aligned with core_finance MAX_MERCHANT_LENGTH by convention (not by import).
  MAX_MERCHANT_LENGTH: int = 200
  ```
- `src/emerald/iam/domain/models/entities/refresh_token.py` — add to class docstring: note about intentionally not using TimestampedMixin (lightweight, create-then-revoke lifecycle)
- `src/emerald/iam/domain/models/entities/password_reset_token.py` — add to class docstring: same note about intentionally not using TimestampedMixin
- `src/emerald/core_finance/domain/models/entities/account_share.py` — add to class docstring: note about intentionally lacking `create()` factory method (created exclusively by parent aggregate)

**Acceptance Criteria:**
- [ ] Alignment comment in integrations constants
- [ ] Design exception comments in all 3 entity docstrings

---

### Phase 2: Token Factory Methods

#### TASK-005: Token Entity Factory Methods
**Layer:** Domain + Application
**Depends On:** None (independent, but grouped in Phase 2 for logical ordering)

**Description:**
Add `create()` classmethods to RefreshToken and PasswordResetToken, then update AuthenticationService to use them.

**Files to Modify:**
- `src/emerald/iam/domain/models/entities/refresh_token.py` — add `create()`:
  ```python
  @classmethod
  def create(
      cls,
      user_id: uuid.UUID,
      token_hash: str,
      family_id: uuid.UUID,
      portal_context: PortalContext,
      expires_at: datetime,
      device_info: str | None = None,
  ) -> RefreshToken:
      return cls(
          id=uuid.uuid4(),
          user_id=user_id,
          token_hash=token_hash,
          family_id=family_id,
          portal_context=portal_context,
          expires_at=expires_at,
          created_at=datetime.now(UTC),
          device_info=device_info,
      )
  ```
  Note: `device_info` is not currently in `__init__` — check if it needs to be added (spec says yes but current entity doesn't have it). If missing, skip `device_info` parameter. The spec signatures serve as guidance; match the actual entity fields.

- `src/emerald/iam/domain/models/entities/password_reset_token.py` — add `create()`:
  ```python
  @classmethod
  def create(
      cls,
      user_id: uuid.UUID,
      token_hash: str,
      expires_at: datetime | None = None,
  ) -> PasswordResetToken:
      return cls(
          id=uuid.uuid4(),
          user_id=user_id,
          token_hash=token_hash,
          expires_at=expires_at,
          created_at=datetime.now(UTC),
      )
  ```

- `src/emerald/iam/application/services/authentication.py` — replace 3 direct `__init__` calls with `create()`:
  1. Line ~104: `RefreshToken(...)` → `RefreshToken.create(...)`
  2. Line ~351: `RefreshToken(...)` → `RefreshToken.create(...)`
  3. Line ~425: `PasswordResetToken(...)` → `PasswordResetToken.create(...)`

**Test Updates:**
- Existing tests that construct RefreshToken/PasswordResetToken directly can remain (for hydration from persistence), but add new tests verifying `create()` auto-generates `id` and `created_at`

**Acceptance Criteria:**
- [ ] Both entities have `create()` classmethods
- [ ] `create()` auto-generates `id` and `created_at`
- [ ] AuthenticationService uses `create()` at all 3 construction sites
- [ ] No test regressions

---

### Phase 3: Card AuditableMixin (Most Involved)

#### TASK-006: Add AuditableMixin to Card Entity
**Layer:** Domain
**Depends On:** None

**Description:**
Add AuditableMixin to Card's inheritance chain and update its constructor and factory.

**Files to Modify:**
- `src/emerald/core_finance/domain/models/entities/card.py`:
  - Import `AuditableMixin` from `emerald.shared_kernel.domain.models.base.auditable`
  - Change class declaration: `class Card(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity):`
  - `create()` factory: add `created_by: uuid.UUID` parameter, pass to constructor
  - All 6 `update_*()` methods: add `updated_by: uuid.UUID` parameter, call `self._set_updated_by(updated_by)` before `self._touch()`

**Acceptance Criteria:**
- [ ] Card inherits `SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity`
- [ ] `Card.create()` accepts and passes `created_by`
- [ ] All 6 update methods accept `updated_by` and call `_set_updated_by()`

---

#### TASK-007: Update Account Aggregate Card Methods
**Layer:** Domain
**Depends On:** TASK-006

**Description:**
Update all Account methods that delegate to Card to accept and forward `updated_by`.

**Files to Modify:**
- `src/emerald/core_finance/domain/models/aggregates/account.py`:
  - `update_card_name(card_id, name, updated_by)` → forward `updated_by` to `card.update_name(name, updated_by)`
  - `update_card_network(card_id, network, updated_by)` → forward to `card.update_network(network, updated_by)`
  - `update_card_expiry(card_id, month, year, updated_by)` → forward to `card.update_expiry(month, year, updated_by)`
  - `update_card_credit_limit(card_id, credit_limit, updated_by)` → forward to `card.update_credit_limit(credit_limit, updated_by)`
  - `update_card_issuing_institution(card_id, institution, updated_by)` → forward to `card.update_issuing_institution(institution, updated_by)`
  - `update_card_notes(card_id, notes, updated_by)` → forward to `card.update_notes(notes, updated_by)`

**Acceptance Criteria:**
- [ ] All 6 `Account.update_card_*()` methods accept and forward `updated_by`

---

#### TASK-008: Update CardManagementService
**Layer:** Application
**Depends On:** TASK-007

**Description:**
Update CardManagementService to pass `requesting_user_id` through the chain.

**Files to Modify:**
- `src/emerald/core_finance/application/services/card_management.py`:
  - `add_card()`: pass `created_by=cmd.requesting_user_id` to `Card.create()`
  - `update_card_name()`: pass `cmd.requesting_user_id` to `account.update_card_name()`
  - `update_card_network()`: pass `cmd.requesting_user_id` to `account.update_card_network()`
  - `update_card_expiry()`: pass `cmd.requesting_user_id` to `account.update_card_expiry()`
  - `update_card_credit_limit()`: pass `cmd.requesting_user_id` to `account.update_card_credit_limit()`
  - `update_card_issuing_institution()`: pass `cmd.requesting_user_id` to `account.update_card_issuing_institution()`
  - `update_card_notes()`: pass `cmd.requesting_user_id` to `account.update_card_notes()`

**Acceptance Criteria:**
- [ ] `add_card()` passes `created_by=cmd.requesting_user_id`
- [ ] All 6 update service methods pass `updated_by=cmd.requesting_user_id`

---

#### TASK-009: Update Card Tests
**Layer:** Tests
**Depends On:** TASK-006, TASK-007, TASK-008

**Description:**
Update all existing card tests and add new audit assertions.

**Test Files to Modify:**
- `tests/unit/core_finance/domain/entities/test_card.py` — all `Card.create()` calls add `created_by`, all `update_*()` calls add `updated_by`, new assertions for `card.created_by` and `card.updated_by`
- `tests/unit/core_finance/domain/aggregates/test_account.py` (card sections) — all `account.update_card_*()` calls add `updated_by`
- `tests/unit/core_finance/application/test_card_management.py` — verify `requesting_user_id` flows through to entity
- `tests/unit/core_finance/fakes.py` — if fake helpers construct Cards, update them with `created_by`

**Acceptance Criteria:**
- [ ] All existing card tests updated for new signatures
- [ ] New tests verify `created_by` is set on card creation
- [ ] New tests verify `updated_by` is set after each update method
- [ ] No test regressions

---

### Phase 4: Final Validation

#### TASK-010: Run Full Quality Suite
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-009

**Description:**
Run all quality gates to ensure no regressions.

**Commands:**
```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

**Acceptance Criteria:**
- [ ] All 2600+ tests pass (plus new tests)
- [ ] No ruff lint violations
- [ ] No ruff format issues
- [ ] No ty type errors

---

## 4. Task Dependency Graph

```
TASK-001 (version init)     ──────────────────────────┐
TASK-002 (constants)        ──────────────────────────┤
TASK-003 (missing events)   ──────────────────────────┤
TASK-004 (docs/comments)    ──────────────────────────┤
TASK-005 (token factories)  ──────────────────────────┤
                                                      │
TASK-006 (card entity)      ─► TASK-007 (account) ──┐ │
                                 │                  │ │
                                 ▼                  │ │
                            TASK-008 (service)  ────┤ │
                                                    │ │
                            TASK-009 (card tests) ──┤ │
                                                    ▼ ▼
                                              TASK-010 (validate)
```

Tasks 1–5 are fully independent and can be done in any order or in parallel.
Tasks 6→7→8 are sequential (each builds on the previous).
Task 9 depends on 6, 7, 8 (all card changes must be in place).
Task 10 is the final gate.

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Card AuditableMixin breaks existing test helpers | Medium | Low | Grep for all `Card(` and `Card.create(` calls in tests, update systematically |
| RefreshToken.create() signature mismatch with spec | Low | Low | Match actual entity fields, not spec's simplified signature |
| Version=1 change breaks assertion in tests | Medium | Low | Search for `version == 0` or `.version` assertions, update them |
| Missing `__init__.py` re-exports for new events | Low | Medium | Verify both events `__init__.py` and context `__init__.py` |

---

## 6. Definition of Done

- [ ] All 10 tasks completed
- [ ] All acceptance criteria met per task
- [ ] `uv run pytest` — all tests pass (2600+ existing + ~20 new)
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format --check .` — clean
- [ ] `uv run ty check` — clean
- [ ] All new events exported in context `__init__.py`
- [ ] All new constants exported in context `__init__.py`

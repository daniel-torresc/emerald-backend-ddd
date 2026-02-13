# Spec 011: Card Management — Implementation Plan

**Spec:** `.specs/spec-011-card-management/spec.md`
**Version:** 1.0
**Date:** 2026-02-13

---

## 1. Overview

This plan implements the Card entity as a child of the Account aggregate, following the exact same pattern as AccountShare. Cards provide metadata enrichment for transactions — tracking which payment card was used for each transaction. The implementation adds value objects (CardNumber with Luhn validation, CardType, CardNetwork), the Card entity, Account aggregate extensions for card lifecycle/updates/queries/cascade, Transaction.update_card_id() for card linking, and a CardManagementService for orchestration.

**Approach:** Inside-out (Domain → Application), split into two phases:
- **Phase 1 (Domain Layer):** Value objects, Card entity, exceptions, events, constants, Account aggregate extensions, Transaction extension
- **Phase 2 (Application Layer):** Commands, CardManagementService, public API exports

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| CardNumber, CardType, CardNetwork | Domain / Value Objects | `card_number.py`, `card_type.py`, `card_network.py` |
| Card entity | Domain / Entities | `card.py` |
| Card events | Domain / Events | `card_events.py` + extend `transaction_events.py` |
| Card exceptions | Domain / Exceptions | `card_exceptions.py` |
| Domain constants | Domain | `constants.py` (modified) |
| Account card management | Domain / Aggregates | `account.py` (modified) |
| Transaction card linking | Domain / Entities | `transaction.py` (modified) |
| Card commands | Application / Commands | `card_commands.py` |
| CardManagementService | Application / Services | `card_management.py` |

### 2.2 Component Diagram

```
CardManagementService (Application)
  │
  ├── uses ──► AbstractCoreFinanceUnitOfWork
  │               ├── accounts: AccountRepository
  │               └── transactions: TransactionRepository
  │
  ├── uses ──► RetentionPolicyService
  │
  └── orchestrates ──► Account (Aggregate)
                         ├── _cards: list[Card]  ◄── NEW
                         │     └── Card (child entity)
                         │           ├── CardNumber (VO)
                         │           ├── CardType (VO)
                         │           └── CardNetwork (VO)
                         └── _shares: list[AccountShare]  (existing)
```

### 2.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Card as child entity (not aggregate) | Cards are managed through Account; no separate repository needed |
| Card events emitted by Account | Follows AccountShare pattern — parent aggregate owns event emission |
| No CardRepository | Cards persisted via `AccountRepository.save(account)` |
| Luhn validation in CardNumber VO | Follows IBAN pattern — complex validation in `__post_init__` |
| Historical card linking allowed | Transactions can reference deleted cards for audit trail |
| Cascade soft-delete without individual events | `AccountSoftDeleted` implies all children deleted |

---

## 3. Implementation Tasks

### Phase 1: Domain Layer

#### TASK-001: Add domain constants for cards

**Layer:** Domain
**Depends On:** None

**Description:**
Add card-related constants to `core_finance/domain/constants.py`.

**Files:**
- `src/emerald/core_finance/domain/constants.py` — Add 7 constants: `MAX_CARDS_PER_ACCOUNT`, `MAX_CARD_NAME_LENGTH`, `MAX_CARD_NOTES_LENGTH`, `MAX_CARD_ISSUING_INSTITUTION_LENGTH`, `MIN_CARD_EXPIRY_YEAR_OFFSET`, `MIN_CARD_NUMBER_LENGTH`, `MAX_CARD_NUMBER_LENGTH`

**Acceptance Criteria:**
- [ ] All 7 constants defined with values from spec section 4

---

#### TASK-002: Create CardType and CardNetwork value objects

**Layer:** Domain / Value Objects
**Depends On:** None

**Description:**
Create two simple enum value objects: `CardType` (CREDIT, DEBIT) and `CardNetwork` (VISA, MASTERCARD, AMERICAN_EXPRESS, DISCOVER, OTHER). Follow the `ImportSourceType`/`ReviewStatus` enum pattern.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/card_type.py` — NEW: CardType enum
- `src/emerald/core_finance/domain/models/value_objects/card_network.py` — NEW: CardNetwork enum

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_card_type.py` — NEW: enum membership, string values
- `tests/unit/core_finance/domain/value_objects/test_card_network.py` — NEW: enum membership, string values

**Acceptance Criteria:**
- [ ] CardType has CREDIT and DEBIT members
- [ ] CardNetwork has VISA, MASTERCARD, AMERICAN_EXPRESS, DISCOVER, OTHER members
- [ ] Tests verify all enum members

---

#### TASK-003: Create CardNumber value object with Luhn validation

**Layer:** Domain / Value Objects
**Depends On:** TASK-001 (constants)

**Description:**
Create the `CardNumber` value object following the IBAN pattern. `@dataclass(frozen=True)` with `value` (normalized digits) and `last_four` (derived). Validation in `__post_init__`: normalize (strip, remove dashes/spaces), digits-only check, length check (13-19), Luhn checksum. Methods: `masked()` → `"****1234"`, `__str__()` → full number.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/card_number.py` — NEW: CardNumber VO

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_card_number.py` — NEW: valid numbers, normalization, last_four derivation, masked(), Luhn failures, length failures, non-numeric failures, whitespace/dash handling

**Acceptance Criteria:**
- [ ] Valid card numbers accepted (e.g., `4111111111111111` Visa test number)
- [ ] Normalization strips whitespace and dashes
- [ ] `last_four` correctly derived
- [ ] `masked()` returns `"****NNNN"` format
- [ ] Invalid Luhn checksum raises `InvalidCardNumberError`
- [ ] Too short/long numbers raise `InvalidCardNumberError`
- [ ] Non-numeric input raises `InvalidCardNumberError`
- [ ] Frozen/immutable dataclass

---

#### TASK-004: Create card exceptions

**Layer:** Domain / Exceptions
**Depends On:** None

**Description:**
Create card-specific exceptions following the `account_exceptions.py` pattern. All extend shared kernel exception hierarchy.

**Files:**
- `src/emerald/core_finance/domain/exceptions/card_exceptions.py` — NEW: 6 exceptions

**Exceptions:**
| Exception | Base | Code |
|-----------|------|------|
| `InvalidCardNumberError` | `InvalidValueError` | `INVALID_CARD_NUMBER` |
| `InvalidCardDataError` | `InvalidValueError` | `INVALID_CARD_DATA` |
| `InvalidCreditLimitError` | `InvalidValueError` | `INVALID_CREDIT_LIMIT` |
| `CardNotFoundError` | `NotFoundError` | `CARD_NOT_FOUND` |
| `MaxCardsReachedError` | `InvariantViolationError` | `MAX_CARDS_REACHED` |
| `CurrencyMismatchError` | `InvariantViolationError` | `CARD_CURRENCY_MISMATCH` |

**Acceptance Criteria:**
- [ ] All 6 exceptions defined with correct base classes and codes
- [ ] Each has customizable message with sensible default

---

#### TASK-005: Create card domain events

**Layer:** Domain / Events
**Depends On:** None

**Description:**
Create card events in a new `card_events.py` file. All use `aggregate_type = "account"` since Card is an Account child entity. Also extend `transaction_events.py` with `TransactionCardLinked` and `TransactionCardUnlinked`.

**Files:**
- `src/emerald/core_finance/domain/events/card_events.py` — NEW: `CardCreated`, `CardUpdated`, `CardSoftDeleted`, `CardRecovered`
- `src/emerald/core_finance/domain/events/transaction_events.py` — MODIFIED: Add `TransactionCardLinked`, `TransactionCardUnlinked`

**Acceptance Criteria:**
- [ ] 4 card events with `aggregate_type = "account"` and correct fields
- [ ] 2 transaction events with `aggregate_type = "transaction"` and correct fields
- [ ] `CardUpdated` includes `changed_fields: list[str]` with `field(default_factory=list)`
- [ ] All events are frozen dataclasses extending `DomainEvent`

---

#### TASK-006: Create Card entity

**Layer:** Domain / Entities
**Depends On:** TASK-001, TASK-002, TASK-003, TASK-004

**Description:**
Create the Card child entity: `Card(SoftDeletableMixin, TimestampedMixin, Entity)`. Immutable fields (`account_id`, `card_type`, `card_number`) via `@property` with private `_field` storage. Factory method `Card.create()` with validation. Six update methods that mutate fields and touch `updated_at`. No `_events` list — parent Account emits events.

**Files:**
- `src/emerald/core_finance/domain/models/entities/card.py` — NEW: Card entity

**Tests:**
- `tests/unit/core_finance/domain/entities/test_card.py` — NEW: factory, immutable fields, update methods, validation, soft-delete/recover lifecycle

**Acceptance Criteria:**
- [ ] `Card.create()` validates name (non-empty, max 100), expiry (month 1-12, year >= current-10), credit_limit (positive if provided)
- [ ] Immutable fields exposed as properties, no setters
- [ ] 6 update methods validate inputs and touch `updated_at`
- [ ] `update_name()` validates non-empty, max length, trims
- [ ] `update_expiry()` validates month 1-12, year range
- [ ] `update_credit_limit()` validates positive if provided
- [ ] `update_issuing_institution()` validates max length, trims
- [ ] `update_notes()` validates max length, trims
- [ ] `update_network()` accepts `CardNetwork | None`
- [ ] Inherits soft_delete/recover from SoftDeletableMixin
- [ ] Hydration constructor accepts `**kwargs: Any` for MRO

---

#### TASK-007: Extend Account aggregate with card management

**Layer:** Domain / Aggregates
**Depends On:** TASK-005, TASK-006

**Description:**
Extend the Account aggregate with `_cards: list[Card]` collection (initialized from `cards` parameter). Add card lifecycle methods (`add_card`, `remove_card`, `recover_card`), card update delegation methods (6 methods), card query methods (`get_card`, `get_cards`, `active_card_count` property), and cascade soft-delete for active cards BEFORE shares revocation in `soft_delete()`.

**Files:**
- `src/emerald/core_finance/domain/models/aggregates/account.py` — MODIFIED: Add _cards, all card methods, cascade

**Tests:**
- `tests/unit/core_finance/domain/aggregates/test_account_cards.py` — NEW: add_card, remove_card, recover_card, update delegation, query methods, cascade, card limit, currency mismatch, active/deleted card filtering

**Acceptance Criteria:**
- [ ] `_cards` initialized from `cards` parameter (default empty list)
- [ ] `add_card()` validates: account active, card.account_id matches, max cards, currency match; emits `CardCreated`
- [ ] `remove_card()` finds card, delegates to `card.soft_delete()`, emits `CardSoftDeleted`
- [ ] `recover_card()` validates account active, finds card, delegates to `card.recover()`, emits `CardRecovered`
- [ ] 6 update methods find active card, delegate to card method, emit `CardUpdated` with changed_fields
- [ ] `update_card_credit_limit()` validates currency match with account
- [ ] `get_card(include_deleted=False)` filters by active/all
- [ ] `get_cards(include_deleted=False)` returns filtered list
- [ ] `active_card_count` property counts non-deleted cards
- [ ] `soft_delete()` cascades to active cards BEFORE share revocation, no individual card events
- [ ] `recover()` does NOT auto-recover cards
- [ ] Deleted cards treated as not-found for update methods (raises `CardNotFoundError`)

---

#### TASK-008: Extend Transaction entity with update_card_id

**Layer:** Domain / Entities
**Depends On:** TASK-005 (transaction events)

**Description:**
Add `update_card_id(card_id: UUID | None)` to Transaction. If linking (new card_id differs from current), set card_id, touch, emit `TransactionCardLinked`. If unlinking (card_id=None and current is not None), clear card_id, touch, emit `TransactionCardUnlinked`. If unchanged, no-op (idempotent). No validation of card existence — that's the service's responsibility.

**Files:**
- `src/emerald/core_finance/domain/models/entities/transaction.py` — MODIFIED: Add `update_card_id()` method

**Tests:**
- `tests/unit/core_finance/domain/entities/test_transaction_card_linking.py` — NEW: link, unlink, re-link, no-op cases, events

**Acceptance Criteria:**
- [ ] Linking to a new card emits `TransactionCardLinked` with transaction_id, card_id, account_id
- [ ] Unlinking (set to None) emits `TransactionCardUnlinked` with transaction_id, previous_card_id, account_id
- [ ] Re-linking (changing card) emits `TransactionCardLinked`
- [ ] Idempotent: linking to same card_id is no-op
- [ ] Idempotent: unlinking when already None is no-op
- [ ] `updated_at` touched on actual changes

---

#### TASK-009: Update domain layer exports

**Layer:** Domain
**Depends On:** TASK-002 through TASK-008

**Description:**
Update all `__init__.py` files in the domain layer to export new types: value objects `__init__.py`, entities `__init__.py`, events `__init__.py`, exceptions `__init__.py`, and the domain `__init__.py`.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/__init__.py` — Add CardNumber, CardType, CardNetwork
- `src/emerald/core_finance/domain/models/entities/__init__.py` — Add Card
- `src/emerald/core_finance/domain/events/__init__.py` — Add card events + transaction card events
- `src/emerald/core_finance/domain/exceptions/__init__.py` — Add card exceptions
- `src/emerald/core_finance/domain/__init__.py` — Add all new domain types

**Acceptance Criteria:**
- [ ] All new types importable from their respective `__init__.py`
- [ ] All new types listed in `__all__` exports

---

### Phase 2: Application Layer

#### TASK-010: Create card commands

**Layer:** Application / Commands
**Depends On:** TASK-002 (CardType, CardNetwork for type references)

**Description:**
Create all card commands in `card_commands.py`. 3 lifecycle commands (`AddCard`, `RemoveCard`, `RecoverCard`), 6 update commands, and 2 card-transaction linking commands. All are `@dataclass(frozen=True)` extending `Command` with UUID sentinel defaults. Commands use primitive types (str, int, Decimal) not domain VOs — conversion happens in the service.

**Files:**
- `src/emerald/core_finance/application/dtos/commands/card_commands.py` — NEW: 11 commands

**Acceptance Criteria:**
- [ ] All 11 commands defined as frozen dataclasses
- [ ] Correct default sentinel values for all fields
- [ ] `AddCard` includes all creation fields (card_type as str, card_number as str, etc.)
- [ ] `UpdateCardCreditLimit` uses `Decimal | None` for amount, `str | None` for currency
- [ ] Linking commands include account_id, transaction_id, card_id, requesting_user_id

---

#### TASK-011: Create CardManagementService

**Layer:** Application / Services
**Depends On:** TASK-007, TASK-008, TASK-010

**Description:**
Create `CardManagementService` with `uow` and `retention_policy_service` dependencies. Implements: `add_card()`, 6 update methods, `remove_card()`, `recover_card()`, `link_transaction_to_card()`, `unlink_transaction_from_card()`. Helper methods: `_load_account()`, `_verify_editor()`, `_verify_owner()`.

**Files:**
- `src/emerald/core_finance/application/services/card_management.py` — NEW: CardManagementService

**Tests:**
- `tests/unit/core_finance/application/test_card_management_service.py` — NEW: all service methods, permission checks, error cases, card-transaction linking/unlinking

**Key behaviors:**
- `add_card()`: builds CardNumber, CardType, CardNetwork, Money from primitives; calls Card.create() + account.add_card()
- `remove_card()`: loads account with `include_deleted=True` (so card's AlreadyDeletedError fires)
- `recover_card()`: loads account (active only), requires OWNER permission
- `link_transaction_to_card()`: validates card exists in account (include_deleted=True for historical linking), validates transaction exists and belongs to same account, validates transaction is active
- `unlink_transaction_from_card()`: validates transaction exists, belongs to account, is active

**Acceptance Criteria:**
- [ ] `add_card()` builds VOs from primitives, creates card, adds to account, saves, returns card
- [ ] 6 update methods load account, verify EDITOR, delegate to account, save
- [ ] `remove_card()` uses include_deleted=True, verifies EDITOR, gets retention, delegates
- [ ] `recover_card()` verifies OWNER permission
- [ ] `link_transaction_to_card()` validates card exists (include_deleted=True), transaction in same account, transaction active
- [ ] `unlink_transaction_from_card()` validates transaction in account, active
- [ ] Permission errors raised correctly (EDITOR for most, OWNER for recover)
- [ ] AccountNotFoundError raised for missing accounts
- [ ] TransactionNotFoundError raised for missing transactions
- [ ] CardNotFoundError raised for missing cards in linking

---

#### TASK-012: Update application layer exports

**Layer:** Application
**Depends On:** TASK-010, TASK-011

**Description:**
Update all `__init__.py` files in the application layer and the context root `__init__.py` to export new types.

**Files:**
- `src/emerald/core_finance/application/dtos/commands/__init__.py` — Add all card commands
- `src/emerald/core_finance/application/services/__init__.py` — Add CardManagementService
- `src/emerald/core_finance/application/__init__.py` — Add all card-related exports
- `src/emerald/core_finance/__init__.py` — Add all card-related exports to context public API

**Acceptance Criteria:**
- [ ] All card commands importable from commands `__init__.py`
- [ ] CardManagementService importable from services `__init__.py`
- [ ] All types listed in `__all__` at each level
- [ ] All types importable from `emerald.core_finance`

---

## 4. Task Dependency Graph

```
TASK-001 (constants) ──┬──► TASK-003 (CardNumber) ──┬──► TASK-006 (Card entity) ──┐
                       │                             │                              │
TASK-002 (enums) ──────┼─────────────────────────────┘                              │
                       │                                                            │
TASK-004 (exceptions) ─┼────────────────────────────────────────────────────────────►├──► TASK-007 (Account extensions)
                       │                                                            │
TASK-005 (events) ─────┼──► TASK-008 (Transaction.update_card_id) ──────────────────┤
                       │                                                            │
                       └────────────────────────────────────────────────────────────►├──► TASK-009 (domain exports)
                                                                                    │
TASK-010 (commands) ───────────────────────────────────────────────────────────────►├──► TASK-011 (CardManagementService)
                                                                                    │
                                                                                    └──► TASK-012 (app exports)
```

**Parallelizable groups:**
- TASK-001, TASK-002, TASK-004, TASK-005 can run in parallel
- TASK-003 depends on TASK-001; TASK-006 depends on TASK-001+002+003+004
- TASK-007 depends on TASK-005+006; TASK-008 depends on TASK-005
- TASK-010 can start as soon as TASK-002 is done
- TASK-011 depends on TASK-007+008+010
- TASK-009 and TASK-012 are export tasks done after their respective phases

---

## 5. File Inventory

### New Files (14)

| File | Description |
|------|-------------|
| `src/emerald/core_finance/domain/models/value_objects/card_number.py` | CardNumber VO with Luhn |
| `src/emerald/core_finance/domain/models/value_objects/card_type.py` | CardType enum |
| `src/emerald/core_finance/domain/models/value_objects/card_network.py` | CardNetwork enum |
| `src/emerald/core_finance/domain/models/entities/card.py` | Card child entity |
| `src/emerald/core_finance/domain/events/card_events.py` | 4 card events |
| `src/emerald/core_finance/domain/exceptions/card_exceptions.py` | 6 card exceptions |
| `src/emerald/core_finance/application/dtos/commands/card_commands.py` | 11 card commands |
| `src/emerald/core_finance/application/services/card_management.py` | CardManagementService |
| `tests/unit/core_finance/domain/value_objects/test_card_number.py` | CardNumber tests |
| `tests/unit/core_finance/domain/value_objects/test_card_type.py` | CardType tests |
| `tests/unit/core_finance/domain/value_objects/test_card_network.py` | CardNetwork tests |
| `tests/unit/core_finance/domain/entities/test_card.py` | Card entity tests |
| `tests/unit/core_finance/domain/aggregates/test_account_cards.py` | Account card mgmt tests |
| `tests/unit/core_finance/domain/entities/test_transaction_card_linking.py` | Transaction card link tests |
| `tests/unit/core_finance/application/test_card_management_service.py` | Service tests |

### Modified Files (10)

| File | Changes |
|------|---------|
| `src/emerald/core_finance/domain/constants.py` | Add 7 card constants |
| `src/emerald/core_finance/domain/models/aggregates/account.py` | Add _cards, card methods, cascade |
| `src/emerald/core_finance/domain/models/entities/transaction.py` | Add update_card_id() |
| `src/emerald/core_finance/domain/events/transaction_events.py` | Add 2 card linking events |
| `src/emerald/core_finance/domain/models/value_objects/__init__.py` | Export new VOs |
| `src/emerald/core_finance/domain/models/entities/__init__.py` | Export Card |
| `src/emerald/core_finance/domain/events/__init__.py` | Export new events |
| `src/emerald/core_finance/domain/exceptions/__init__.py` | Export new exceptions |
| `src/emerald/core_finance/domain/__init__.py` | Export all new domain types |
| `src/emerald/core_finance/application/dtos/commands/__init__.py` | Export card commands |
| `src/emerald/core_finance/application/services/__init__.py` | Export CardManagementService |
| `src/emerald/core_finance/application/__init__.py` | Export all new app types |
| `src/emerald/core_finance/__init__.py` | Export all new context types |

### No Changes Needed

| File | Reason |
|------|--------|
| `shared_kernel/.../deletable_entity_type.py` | `CARD` member already exists |
| `application/ports/outbound/unit_of_work.py` | Cards persisted through Account aggregate |
| `tests/unit/core_finance/fakes.py` | No new fakes needed (cards in Account) |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Account `__init__` signature change breaks tests | Medium | Medium | Add `cards` param with `None` default; existing tests unaffected |
| Luhn algorithm edge cases | Low | Medium | Use well-known test card numbers (Visa 4111..., MC 5500..., Amex 3782...) |
| Account soft_delete cascade ordering | Low | High | Test cascade order: cards → shares → super().soft_delete() |
| Transaction.update_card_id event mismatch | Low | Medium | Test all 4 cases: link, re-link, unlink, no-op |

---

## 7. Definition of Done

- [ ] All 12 tasks completed
- [ ] All acceptance criteria met
- [ ] All new unit tests passing
- [ ] All existing 1806 tests still passing (no regressions)
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format .` — clean
- [ ] `uv run ty check` — clean
- [ ] All new types exported in `__init__.py` at every level

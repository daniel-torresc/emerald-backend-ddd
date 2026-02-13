# Spec 011: Card Management

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 007 (Account Management), 009 (Transaction Management)
**Date:** 2026-02-13

---

## 1. Overview

This spec defines the Card entity — a representation of physical or virtual payment cards linked to a financial account. Cards serve as metadata enrichment for transactions, allowing users to track which card was used for a given payment. Cards are **child entities of the Account aggregate**, following the same ownership pattern as AccountShare.

**Key Principle:** Cards are informational entities attached to accounts. They do not enforce financial constraints — they provide organizational context for transactions. A card's primary purpose is to answer "which card was used?" for any given transaction.

---

## 2. Background & Context

### Problem Statement

Users hold multiple payment cards (credit, debit) across different financial institutions. When recording or importing transactions, they need to associate each transaction with the specific card used. Without card tracking, users lose visibility into per-card spending patterns and cannot distinguish between transactions on different cards within the same account.

### Business Goals

- Enable per-card transaction tracking and filtering
- Support both credit and debit card metadata
- Preserve card history even after card expiry or cancellation (soft delete)
- Maintain referential integrity between cards and transactions without cascading data loss

### Success Metrics

- Cards can be created, updated, and soft-deleted within accounts
- Transactions can be linked/unlinked to cards with same-account validation
- Card deletion preserves transaction history (card_id retained on transactions)
- Account soft-delete cascades to cards

---

## 3. Scope

### In Scope

- Card entity as Account aggregate child (like AccountShare)
- CardNumber (full PAN with Luhn validation, like IBAN), CardType, CardNetwork value objects
- Card creation, update, and soft-delete lifecycle
- Card-transaction linking via `Transaction.update_card_id()`
- Account aggregate extensions for card management
- CardManagementService (application layer)
- Domain events, exceptions, and commands
- Account soft-delete cascade to cards
- DeletableEntityType.CARD addition

### Out of Scope

- Card transaction processing or payment initiation
- Card balance tracking (credit limit is informational only)
- Bank-imported card data mapping (Spec 015)
- Card expiration enforcement (expired cards remain usable for historical linking)

---

## 4. Domain Constants

New constants in `core_finance/domain/constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_CARDS_PER_ACCOUNT` | 10 | Maximum active cards per account |
| `MAX_CARD_NAME_LENGTH` | 100 | Card display name max length |
| `MAX_CARD_NOTES_LENGTH` | 500 | Card notes max length |
| `MAX_CARD_ISSUING_INSTITUTION_LENGTH` | 200 | Issuing institution name max length |
| `MIN_CARD_EXPIRY_YEAR_OFFSET` | -10 | Minimum expiry year relative to current year |
| `MIN_CARD_NUMBER_LENGTH` | 13 | Minimum card number length |
| `MAX_CARD_NUMBER_LENGTH` | 19 | Maximum card number length |

---

## 5. Value Objects

### 5.1 CardNumber

`@dataclass(frozen=True)` value object — follows the same pattern as `IBAN`. Stores the full card number (PAN), derives `last_four`, and provides `masked()` display.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Full card number, digits only (normalized) |
| last_four | str | Derived: last 4 digits of the card number |

**Validation (`__post_init__`):**

1. **Normalize:** strip whitespace, remove dashes/spaces
2. **Digits only:** all characters must be numeric (0-9) — raises `InvalidCardNumberError`
3. **Length:** between `MIN_CARD_NUMBER_LENGTH` (13) and `MAX_CARD_NUMBER_LENGTH` (19) — raises `InvalidCardNumberError`
4. **Luhn checksum:** validate using Luhn algorithm (ISO/IEC 7812) — raises `InvalidCardNumberError`
5. **Store** normalized value and derive `last_four` via `object.__setattr__`

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `masked()` | str | Masked display: `"****1234"` (like IBAN.masked()) |
| `__str__()` | str | Returns the full card number |

### 5.2 CardType

`Enum` value object.

| Value | Description |
|-------|-------------|
| `CREDIT` | Credit card |
| `DEBIT` | Debit card |

### 5.3 CardNetwork

`Enum` value object.

| Value | Description |
|-------|-------------|
| `VISA` | Visa network |
| `MASTERCARD` | Mastercard network |
| `AMERICAN_EXPRESS` | American Express network |
| `DISCOVER` | Discover network |
| `OTHER` | Other/unknown network |

---

## 6. Card Entity

### 6.1 Composition

```
Card(SoftDeletableMixin, TimestampedMixin, Entity)
```

Card is a **child entity** of the Account aggregate. It does NOT have its own `_events` list — all events are emitted by the parent Account. Card uses `SoftDeletableMixin` for full soft-delete lifecycle with retention scheduling.

### 6.2 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique card identifier |
| account_id | UUID | No | Parent account (immutable) |
| card_type | CardType | No | Credit or Debit (immutable) |
| card_name | str | Yes | User-defined display name |
| card_number | CardNumber | No | Full card number with Luhn validation (immutable) |
| card_network | CardNetwork \| None | Yes | Visa, Mastercard, etc. |
| expiry_month | int | Yes | Expiration month (1-12) |
| expiry_year | int | Yes | Expiration year (4-digit) |
| credit_limit | Money \| None | Yes | For credit cards (informational) |
| issuing_institution | str \| None | Yes | Card issuer name |
| notes | str \| None | Yes | User notes |
| created_at | datetime | No | From TimestampedMixin |
| updated_at | datetime | Auto | From TimestampedMixin |
| deleted_at | datetime \| None | Auto | From SoftDeletableMixin |
| deleted_by | UUID \| None | Auto | From SoftDeletableMixin |

### 6.3 Immutable Fields

| Field | Rationale |
|-------|-----------|
| card_type | Fundamental card characteristic doesn't change |
| card_number | Physical card identifier doesn't change |
| account_id | Cards don't move between accounts |

Immutable fields exposed via `@property` (stored as `_card_type`, `_card_number`, `_account_id`).

### 6.4 Factory Method

```
Card.create(
    account_id: UUID,
    card_type: CardType,
    card_name: str,
    card_number: CardNumber,
    expiry_month: int,
    expiry_year: int,
    card_network: CardNetwork | None = None,
    credit_limit: Money | None = None,
    issuing_institution: str | None = None,
    notes: str | None = None,
) -> Card
```

**Validates:**
- `card_name`: non-empty after trimming, max `MAX_CARD_NAME_LENGTH` chars
- `expiry_month`: 1-12
- `expiry_year`: >= current year - `MIN_CARD_EXPIRY_YEAR_OFFSET` (e.g., >= 2016 in 2026)
- `credit_limit`: positive if provided (currency match validated by Account)
- `issuing_institution`: max `MAX_CARD_ISSUING_INSTITUTION_LENGTH` chars if provided, trimmed
- `notes`: max `MAX_CARD_NOTES_LENGTH` chars if provided, trimmed

**Raises:** `InvalidCardDataError` (name, expiry), `InvalidCreditLimitError` (zero/negative limit)

**Note:** Does NOT validate credit_limit currency — that is the Account's responsibility in `add_card()`.

### 6.5 Update Methods

Card has self-mutation methods that update fields and touch `updated_at`. These methods do NOT emit events — the parent Account emits `CardUpdated` via its delegation methods.

| Method | Validates | Updates |
|--------|-----------|---------|
| `update_name(card_name: str)` | Non-empty, max length, trimmed | card_name, updated_at |
| `update_network(card_network: CardNetwork \| None)` | — | card_network, updated_at |
| `update_expiry(month: int, year: int)` | month 1-12, year >= min | expiry_month, expiry_year, updated_at |
| `update_credit_limit(credit_limit: Money \| None)` | Positive if provided | credit_limit, updated_at |
| `update_issuing_institution(institution: str \| None)` | Max length, trimmed | issuing_institution, updated_at |
| `update_notes(notes: str \| None)` | Max length, trimmed | notes, updated_at |

**Note:** `update_credit_limit()` validates that the amount is positive but does NOT validate currency match — that is the Account's responsibility in `update_card_credit_limit()`.

### 6.6 Lifecycle

Card inherits `soft_delete(deleted_by, retention, reason)` and `recover()` from `SoftDeletableMixin`. No overrides needed.

### 6.7 Hydration Constructor

For repository reconstruction:

```
Card(
    id: UUID,
    account_id: UUID,
    card_type: CardType,
    card_name: str,
    card_number: CardNumber,
    expiry_month: int,
    expiry_year: int,
    card_network: CardNetwork | None = None,
    credit_limit: Money | None = None,
    issuing_institution: str | None = None,
    notes: str | None = None,
    **kwargs: Any,  # MRO forwarding for mixins
)
```

---

## 7. Account Aggregate Extensions

### 7.1 Card Collection

Account gains a `_cards: list[Card]` collection, initialized from a `cards` parameter (like `_shares` from `shares`).

```python
def __init__(self, *, cards: list[Card] | None = None, **kwargs):
    ...
    self._cards: list[Card] = cards if cards is not None else []
```

### 7.2 Card Lifecycle Methods

#### `add_card(card: Card) -> None`

**Validates:**
1. Account is active — raises `AccountNotActiveError`
2. `card.account_id == self.id` — raises `InvalidCardDataError`
3. Active card count < `MAX_CARDS_PER_ACCOUNT` — raises `MaxCardsReachedError`
4. If `card.credit_limit` is provided, `card.credit_limit.currency == self.currency` — raises `CurrencyMismatchError`

**Effect:** Appends card to `_cards`, emits `CardCreated`, touches.

#### `remove_card(card_id: UUID, deleted_by: UUID, retention: RetentionPeriod, reason: str | None = None) -> None`

**Validates:**
1. Card exists in this account — raises `CardNotFoundError`
2. Card is active (not already deleted) — `SoftDeletableMixin` raises `AlreadyDeletedError`

**Effect:** Calls `card.soft_delete(deleted_by, retention, reason)`, emits `CardSoftDeleted`, touches.

#### `recover_card(card_id: UUID) -> None`

**Validates:**
1. Account is active — raises `AccountNotActiveError`
2. Card exists in this account — raises `CardNotFoundError`
3. Card is deleted — `SoftDeletableMixin` raises `NotDeletedError`

**Effect:** Calls `card.recover()`, emits `CardRecovered`, touches.

### 7.3 Card Update Methods

Each update method finds the card, validates it's active, delegates to Card's self-mutation method, emits `CardUpdated`, and touches.

| Account Method | Delegates To | Extra Validation |
|----------------|-------------|------------------|
| `update_card_name(card_id, name)` | `card.update_name(name)` | — |
| `update_card_network(card_id, network)` | `card.update_network(network)` | — |
| `update_card_expiry(card_id, month, year)` | `card.update_expiry(month, year)` | — |
| `update_card_credit_limit(card_id, credit_limit)` | `card.update_credit_limit(credit_limit)` | Currency match: `credit_limit.currency == self.currency` |
| `update_card_issuing_institution(card_id, institution)` | `card.update_issuing_institution(institution)` | — |
| `update_card_notes(card_id, notes)` | `card.update_notes(notes)` | — |

**Common behavior:**
- Find card by `card_id` — raises `CardNotFoundError` if not found
- Validate card is active (not deleted) — raises `CardNotFoundError` (treat deleted cards as not found for updates)
- Delegate to card method
- Emit `CardUpdated(card_id, account_id, changed_fields=[field_name])`
- Call `self._touch()`

**Raises:** `CardNotFoundError`, `CurrencyMismatchError` (for credit limit), validation errors from Card methods.

### 7.4 Card Query Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_card(card_id: UUID, include_deleted: bool = False) -> Card \| None` | Card or None | Find card by ID, optionally including deleted |
| `get_cards(include_deleted: bool = False) -> list[Card]` | list[Card] | All cards, optionally including deleted |
| `active_card_count -> int` | int | Property: count of non-deleted cards |

### 7.5 Soft-Delete Cascade

When `Account.soft_delete()` is called, **active cards are cascade soft-deleted** BEFORE `super().soft_delete()`:

```
Account.soft_delete(deleted_by, retention, reason):
    # 1. Cascade soft-delete active cards (no individual CardSoftDeleted events)
    for card in self._cards:
        if card.is_active():
            card.soft_delete(deleted_by, retention)

    # 2. Revoke non-owner shares (existing behavior)
    ...

    # 3. Call super().soft_delete()
    super().soft_delete(deleted_by, retention, reason)
```

**Important:** Cascade soft-delete does NOT emit individual `CardSoftDeleted` events. The `AccountSoftDeleted` event implies all children are also deleted.

### 7.6 Recovery Behavior

When `Account.recover()` is called, **cards are NOT automatically recovered**. Cards remain in their soft-deleted state. Users must individually recover cards via `Account.recover_card()`.

This matches the existing share behavior (recovery does not restore revoked shares).

---

## 8. Transaction Entity Extension

### 8.1 New Method: `update_card_id`

```
Transaction.update_card_id(card_id: UUID | None) -> None
```

**Behavior:**
- If `card_id` is provided and differs from current: sets `self.card_id = card_id`, touches, emits `TransactionCardLinked`
- If `card_id` is `None` and current is not `None`: sets `self.card_id = None`, touches, emits `TransactionCardUnlinked`
- If value is unchanged (same card_id or already None): no-op (idempotent)

**Note:** This method does NOT validate that the card exists or belongs to the same account — that is the **CardManagementService's** responsibility.

---

## 9. Domain Events

### 9.1 Card Events (new file: `card_events.py`)

All card events have `aggregate_type: ClassVar[str] = "account"` since Card is an Account child.

| Event | Trigger | Key Data |
|-------|---------|----------|
| `CardCreated` | `Account.add_card()` | card_id, account_id, card_type (str), card_name, card_number_masked (str) |
| `CardUpdated` | `Account.update_card_*()` | card_id, account_id, changed_fields (list[str]) |
| `CardSoftDeleted` | `Account.remove_card()` | card_id, account_id, deleted_by |
| `CardRecovered` | `Account.recover_card()` | card_id, account_id |

### 9.2 Transaction Events (extend `transaction_events.py`)

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TransactionCardLinked` | `Transaction.update_card_id(card_id)` | transaction_id, card_id, account_id |
| `TransactionCardUnlinked` | `Transaction.update_card_id(None)` | transaction_id, previous_card_id, account_id |

These have `aggregate_type: ClassVar[str] = "transaction"`.

---

## 10. Domain Exceptions

### 10.1 New Exceptions (new file: `card_exceptions.py`)

| Exception | Base | Code | Trigger |
|-----------|------|------|---------|
| `InvalidCardNumberError` | `InvalidValueError` | `INVALID_CARD_NUMBER` | CardNumber fails validation (non-numeric, wrong length, Luhn checksum failure) |
| `InvalidCardDataError` | `InvalidValueError` | `INVALID_CARD_DATA` | Invalid name (empty/too long), invalid expiry month/year |
| `InvalidCreditLimitError` | `InvalidValueError` | `INVALID_CREDIT_LIMIT` | Credit limit is zero or negative |
| `CardNotFoundError` | `NotFoundError` | `CARD_NOT_FOUND` | Card doesn't exist in account or is deleted |
| `MaxCardsReachedError` | `InvariantViolationError` | `MAX_CARDS_REACHED` | Account already has MAX_CARDS_PER_ACCOUNT active cards |
| `CurrencyMismatchError` | `InvariantViolationError` | `CARD_CURRENCY_MISMATCH` | Credit limit currency differs from account currency |

### 10.2 Reused Exceptions

| Exception | Source | Usage |
|-----------|--------|-------|
| `AlreadyDeletedError` | SoftDeletableMixin | Removing an already-deleted card |
| `NotDeletedError` | SoftDeletableMixin | Recovering a non-deleted card |
| `AccountNotActiveError` | account_exceptions | Adding/recovering card on deleted account |

---

## 11. Commands

New file: `card_commands.py`. All commands extend `Command` base from shared kernel.

### 11.1 Card Lifecycle Commands

| Command | Key Fields |
|---------|------------|
| `AddCard` | account_id, requesting_user_id, card_type, card_name, card_number, expiry_month, expiry_year, card_network?, credit_limit_amount?, credit_limit_currency?, issuing_institution?, notes? |
| `RemoveCard` | account_id, card_id, requesting_user_id, reason? |
| `RecoverCard` | account_id, card_id, requesting_user_id |

### 11.2 Card Update Commands

| Command | Key Fields |
|---------|------------|
| `UpdateCardName` | account_id, card_id, requesting_user_id, card_name |
| `UpdateCardNetwork` | account_id, card_id, requesting_user_id, card_network (CardNetwork \| None) |
| `UpdateCardExpiry` | account_id, card_id, requesting_user_id, expiry_month, expiry_year |
| `UpdateCardCreditLimit` | account_id, card_id, requesting_user_id, credit_limit_amount? (Decimal \| None), credit_limit_currency? (str \| None) |
| `UpdateCardIssuingInstitution` | account_id, card_id, requesting_user_id, issuing_institution (str \| None) |
| `UpdateCardNotes` | account_id, card_id, requesting_user_id, notes (str \| None) |

### 11.3 Card-Transaction Linking Commands

| Command | Key Fields |
|---------|------------|
| `LinkTransactionToCard` | account_id, transaction_id, card_id, requesting_user_id |
| `UnlinkTransactionFromCard` | account_id, transaction_id, requesting_user_id |

---

## 12. Application Service

### 12.1 CardManagementService

New service: `CardManagementService` in `core_finance/application/services/card_management.py`.

**Dependencies:**
- `uow: AbstractCoreFinanceUnitOfWork`
- `retention_policy_service: RetentionPolicyService`

**Note:** No `CardRepository` needed — cards are persisted through the Account aggregate.

### 12.2 Service Methods

#### Card Creation

```
add_card(cmd: AddCard) -> Card
    1. Load account (active only)
    2. Verify EDITOR permission (requesting_user_id)
    3. Build CardNumber from cmd.card_number
    4. Build Money from cmd.credit_limit_amount + cmd.credit_limit_currency (if provided)
    5. Call Card.create(...)
    6. Call account.add_card(card)  # validates currency, max cards
    7. Save account, commit
    8. Return card
```

#### Card Updates

All update methods follow the same pattern:

```
update_card_{field}(cmd: UpdateCard{Field}) -> None
    1. Load account (active only)
    2. Verify EDITOR permission
    3. Call account.update_card_{field}(cmd.card_id, ...)
    4. Save account, commit
```

Specific methods:
- `update_card_name(cmd: UpdateCardName)`
- `update_card_network(cmd: UpdateCardNetwork)`
- `update_card_expiry(cmd: UpdateCardExpiry)`
- `update_card_credit_limit(cmd: UpdateCardCreditLimit)` — builds Money from amount+currency if provided
- `update_card_issuing_institution(cmd: UpdateCardIssuingInstitution)`
- `update_card_notes(cmd: UpdateCardNotes)`

#### Card Lifecycle

```
remove_card(cmd: RemoveCard) -> None
    1. Load account (include_deleted=True, so card's AlreadyDeletedError fires before AccountNotActive)
    2. Verify EDITOR permission
    3. Get retention period for DeletableEntityType.CARD
    4. Call account.remove_card(cmd.card_id, cmd.requesting_user_id, retention, cmd.reason)
    5. Save account, commit

recover_card(cmd: RecoverCard) -> None
    1. Load account (active only)
    2. Verify OWNER permission
    3. Call account.recover_card(cmd.card_id)
    4. Save account, commit
```

#### Card-Transaction Linking

```
link_transaction_to_card(cmd: LinkTransactionToCard) -> None
    1. Load account (active only)
    2. Verify EDITOR permission
    3. Verify card exists in account (include_deleted=True — historical linking allowed)
       Raises: CardNotFoundError
    4. Load transaction from repository
       Raises: TransactionNotFoundError
    5. Verify transaction.account_id == account.id
       Raises: TransactionNotInAccountError (or similar)
    6. Verify transaction is active (not deleted)
    7. Call transaction.update_card_id(cmd.card_id)
    8. Save transaction, commit

unlink_transaction_from_card(cmd: UnlinkTransactionFromCard) -> None
    1. Load account (active only)
    2. Verify EDITOR permission
    3. Load transaction from repository
    4. Verify transaction.account_id == account.id
    5. Verify transaction is active
    6. Call transaction.update_card_id(None)
    7. Save transaction, commit
```

### 12.3 Authorization Matrix

| Operation | Required Permission |
|-----------|-------------------|
| Add card | EDITOR |
| Update card (any field) | EDITOR |
| Remove card (soft delete) | EDITOR |
| Recover card | OWNER |
| Link/unlink transaction to card | EDITOR |
| View cards (get_card, get_cards) | VIEWER (enforced at API layer, not domain) |

### 12.4 Helper Methods

```
_load_account(account_id, include_deleted=False) -> Account
    Raises: AccountNotFoundError

_verify_editor(account, requesting_user_id) -> None
    Raises: InsufficientPermissionError if not EDITOR or above

_verify_owner(account, requesting_user_id) -> None
    Raises: InsufficientPermissionError if not OWNER
```

---

## 13. Shared Kernel Extension

### 13.1 DeletableEntityType

Add `CARD` member to `DeletableEntityType` enum in shared kernel.

---

## 14. Validation Rules Summary

| Rule ID | Rule | Enforcement |
|---------|------|-------------|
| CRD-001 | Card must belong to an account | Card.account_id required, immutable |
| CRD-002 | Card number: 13-19 digits, passes Luhn checksum | CardNumber `__post_init__` |
| CRD-003 | Expiry month: 1-12 | Card.create(), Card.update_expiry() |
| CRD-004 | Expiry year: >= current year - 10 | Card.create(), Card.update_expiry() |
| CRD-005 | Credit limit: positive if specified | Card.create(), Card.update_credit_limit() |
| CRD-006 | Credit limit currency matches account | Account.add_card(), Account.update_card_credit_limit() |
| CRD-007 | Card name: non-empty, max 100 chars | Card.create(), Card.update_name() |
| CRD-008 | Notes: max 500 chars | Card.create(), Card.update_notes() |
| CRD-009 | Issuing institution: max 200 chars | Card.create(), Card.update_issuing_institution() |
| CRD-010 | Max 10 active cards per account | Account.add_card() |
| CRD-011 | Card-transaction same account | CardManagementService.link_transaction_to_card() |

---

## 15. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Add card to deleted account | Raises `AccountNotActiveError` |
| Add card exceeding MAX_CARDS_PER_ACCOUNT | Raises `MaxCardsReachedError` |
| Credit limit with wrong currency | Raises `CurrencyMismatchError` |
| Remove already-deleted card | `SoftDeletableMixin` raises `AlreadyDeletedError` |
| Recover non-deleted card | `SoftDeletableMixin` raises `NotDeletedError` |
| Recover card on deleted account | Raises `AccountNotActiveError` |
| Update deleted card | Raises `CardNotFoundError` (deleted = not found for updates) |
| Link transaction to card in different account | Raises `TransactionNotInAccountError` |
| Link transaction to non-existent card | Raises `CardNotFoundError` |
| Link transaction to deleted card | **Allowed** (historical reference preserved) |
| Unlink transaction with no card_id | No-op (idempotent) |
| Account soft-delete with active cards | Cards cascade soft-deleted (no individual events) |
| Account recover with deleted cards | Cards remain deleted (manual recovery required) |
| Delete card used by transactions | Card deleted; transaction.card_id preserved |
| Set credit_limit to None on debit card | Allowed (credit_limit is always optional) |
| Set credit_limit on debit card | Allowed (informational only, no card_type restriction) |

---

## 16. Acceptance Criteria

### Card Creation

- [ ] Card created with valid attributes succeeds
- [ ] Card requires non-empty `card_name` (trimmed) — raises `InvalidCardDataError`
- [ ] Card name exceeding 100 chars raises `InvalidCardDataError`
- [ ] `card_number` must be 13-19 digits and pass Luhn checksum — raises `InvalidCardNumberError`
- [ ] `card_number.last_four` correctly derived from full number
- [ ] `card_number.masked()` returns `"****NNNN"` format
- [ ] `expiry_month` must be 1-12 — raises `InvalidCardDataError`
- [ ] `expiry_year` must be >= current year - 10 — raises `InvalidCardDataError`
- [ ] `credit_limit` must be positive if provided — raises `InvalidCreditLimitError`
- [ ] `credit_limit` currency must match account currency — raises `CurrencyMismatchError`
- [ ] Card on deleted account raises `AccountNotActiveError`
- [ ] Exceeding MAX_CARDS_PER_ACCOUNT raises `MaxCardsReachedError`
- [ ] `CardCreated` event emitted by Account

### Immutable Fields

- [ ] `card_type` cannot be changed after creation (no setter exposed)
- [ ] `card_number` cannot be changed after creation (no setter exposed)
- [ ] `account_id` cannot be changed after creation (no setter exposed)

### Card Updates

- [ ] `card_name` can be updated — validates non-empty, max length
- [ ] `card_network` can be updated (including set to None)
- [ ] `expiry_month`/`expiry_year` can be updated — validates month 1-12, year range
- [ ] `credit_limit` can be updated (including set to None) — validates positive, currency match
- [ ] `issuing_institution` can be updated (including set to None) — validates max length
- [ ] `notes` can be updated (including set to None) — validates max length
- [ ] `updated_at` set on every update
- [ ] `CardUpdated` event emitted by Account with `changed_fields`
- [ ] Updating a deleted card raises `CardNotFoundError`
- [ ] EDITOR permission required for all updates

### Card-Transaction Linking

- [ ] Transaction can be linked to a card in the same account
- [ ] Transaction can be linked to a deleted card (historical reference)
- [ ] Transaction `card_id` can be changed to a different card (re-linking)
- [ ] Transaction `card_id` can be cleared (unlinking)
- [ ] Card and transaction must be in the same account — raises error if not
- [ ] `TransactionCardLinked` event emitted by Transaction
- [ ] `TransactionCardUnlinked` event emitted by Transaction
- [ ] Idempotent: linking to same card or unlinking when already None is no-op
- [ ] EDITOR permission required

### Lifecycle

- [ ] Soft deleting a card does NOT affect linked transactions (`card_id` preserved)
- [ ] Soft deleting a card sets `deleted_at`, `deleted_by`, schedules hard delete
- [ ] `CardSoftDeleted` event emitted by Account
- [ ] Recovering a card requires parent account to be active
- [ ] Recovering a card clears deletion fields
- [ ] `CardRecovered` event emitted by Account
- [ ] EDITOR permission for remove, OWNER permission for recover
- [ ] Soft deleted cards excluded from `get_cards()` by default
- [ ] Soft deleted cards included with `include_deleted=True`

### Account Cascade

- [ ] Account soft-delete cascade soft-deletes all active cards
- [ ] Cascade does NOT emit individual `CardSoftDeleted` events
- [ ] Account recovery does NOT auto-recover cards
- [ ] Cards remain in trash after account recovery

---

## 17. Dependencies

### Internal Dependencies

- **Spec 007 (Account Management):** Account aggregate, AccountRepository, UoW
- **Spec 009 (Transaction Management):** Transaction entity, TransactionRepository
- **Spec 006 (Data Lifecycle):** SoftDeletableMixin, DeletableEntityType, RetentionPolicyService
- **Spec 001 (Shared Kernel):** Entity base, TimestampedMixin, Money, DomainEvent, Command
- **Spec 008 (Account Sharing):** PermissionLevel for authorization checks

### No New Repository

Cards are persisted through the Account aggregate. The `AccountRepository.save(account)` persists all child cards. No `CardRepository` protocol is needed.

The `AbstractCoreFinanceUnitOfWork` does NOT gain a `cards` member — the existing `accounts` repository handles card persistence.

---

## 18. File Structure

```
src/emerald/core_finance/
  domain/
    models/
      entities/
        card.py                    # NEW: Card entity
    value_objects/
      card_number.py              # NEW: CardNumber VO (full PAN, Luhn, masked)
      card_type.py                # NEW: CardType enum
      card_network.py             # NEW: CardNetwork enum
    events/
      card_events.py              # NEW: CardCreated, CardUpdated, CardSoftDeleted, CardRecovered
    exceptions/
      card_exceptions.py          # NEW: Card-specific exceptions
    constants.py                  # MODIFIED: Add card constants
  application/
    commands/
      card_commands.py            # NEW: All card commands
    services/
      card_management.py          # NEW: CardManagementService

# MODIFIED files:
  domain/
    models/
      aggregates/
        account.py                # MODIFIED: Add _cards, card methods, cascade
    models/
      entities/
        transaction.py            # MODIFIED: Add update_card_id()
    events/
      transaction_events.py       # MODIFIED: Add TransactionCardLinked/Unlinked
    __init__.py                   # MODIFIED: Export new types

# Shared kernel:
src/emerald/shared_kernel/
  domain/
    value_objects/
      deletable_entity_type.py    # MODIFIED: Add CARD member

# Tests:
tests/unit/core_finance/
  domain/
    value_objects/
      test_card_number.py         # NEW
      test_card_type.py           # NEW
      test_card_network.py        # NEW
    entities/
      test_card.py                # NEW
    aggregates/
      test_account_cards.py       # NEW: Account card management tests
    test_transaction_card_linking.py  # NEW
  application/
    test_card_management_service.py   # NEW
  fakes.py                        # MODIFIED: No new fakes needed (cards in Account)
```

---

## 19. Glossary

- **Card:** A representation of a physical or virtual payment card, stored as metadata
- **Child Entity:** An entity managed by an aggregate root, with no independent repository
- **Cascade Soft-Delete:** Automatically soft-deleting child entities when the parent is soft-deleted
- **Historical Linking:** Allowing transactions to reference deleted cards for audit trail preservation
- **CardNumber:** Full card number (PAN) validated with Luhn algorithm — stored with derived `last_four` and `masked()` display, following the IBAN pattern
- **Luhn Algorithm:** ISO/IEC 7812 checksum validation for card numbers (also known as MOD-10)

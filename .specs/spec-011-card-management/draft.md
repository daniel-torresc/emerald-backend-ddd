# Spec 011: Card Management

**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 007 (Account Management)
**Blocks:** None

---

## 1. Overview

This spec defines the Card entity — a representation of physical or virtual payment cards linked to a financial account. Cards serve as metadata enrichment for transactions, allowing users to track which card was used for a given payment. Cards are part of the Account aggregate.

**Key Principle:** Cards are informational entities attached to accounts. They do not enforce financial constraints — they provide organizational context for transactions. A card's primary purpose is to answer "which card was used?" for any given transaction.

## 2. Scope

### In Scope

- Card entity with all attributes and invariants
- Card types (Credit, Debit) and networks (Visa, Mastercard, etc.)
- `CardLastFour` value object
- Card creation, update, and soft delete
- Card-transaction linking (setting `card_id` on a transaction)
- Card lifecycle within the Account aggregate

### Out of Scope

- Full card number storage (PCI DSS — only last four digits stored)
- Card transaction processing or payment initiation
- Card balance tracking (credit limit usage is informational only)
- Bank-imported card data mapping (Spec 015)

## 3. Value Objects

### 3.1 CardLastFour

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Exactly 4 numeric characters |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate format | `InvalidCardLastFourError` |
| `__eq__` / `__hash__` | Equality by value | - |
| `__str__() -> str` | Returns the 4 digits | - |

**Business Rules:**

- Exactly 4 characters
- All characters must be numeric digits (0-9)

### 3.2 CardType

**Enum:**

| Value | Description |
|-------|-------------|
| CREDIT | Credit card |
| DEBIT | Debit card |

### 3.3 CardNetwork

**Enum:**

| Value | Description |
|-------|-------------|
| VISA | Visa network |
| MASTERCARD | Mastercard network |
| AMERICAN_EXPRESS | American Express network |
| DISCOVER | Discover network |
| OTHER | Other/unknown network |

## 4. Card Entity

### 4.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| card_id | UUID | No | Unique identifier |
| account_id | UUID | No | Parent account |
| card_type | CardType | No | Credit or Debit (immutable) |
| card_name | str | Yes | User-defined display name |
| last_four_digits | CardLastFour | No | Last 4 digits (immutable) |
| card_network | CardNetwork? | Yes | Visa, Mastercard, etc. |
| expiry_month | int | Yes | Expiration month (1-12) |
| expiry_year | int | Yes | Expiration year (4-digit) |
| credit_limit | Money? | Yes | For credit cards (optional) |
| issuing_institution_id | UUID? | Yes | Card issuer reference |
| notes | str? | Yes | User notes |
| created_at | datetime | No | Creation time |
| updated_at | datetime | Auto | Last update time |
| deleted_at | datetime? | Yes | Soft delete timestamp |

### 4.2 Immutable Fields

| Field | Rationale |
|-------|-----------|
| card_type | Fundamental card characteristic doesn't change |
| last_four_digits | Physical card identifier doesn't change |
| account_id | Cards don't move between accounts |

### 4.3 Domain Methods

```
Card:
  // Creation
  + create(
      account_id: UUID,
      card_type: CardType,
      card_name: str,
      last_four_digits: CardLastFour,
      expiry_month: int,
      expiry_year: int,
      card_network: CardNetwork? = None,
      credit_limit: Money? = None,
      issuing_institution_id: UUID? = None,
      notes: str? = None
    ) -> Card                                          [class method]
      Validates:
        - card_name is non-empty
        - expiry_month is 1-12
        - expiry_year is reasonable (not in distant past)
        - credit_limit is positive if provided
        - credit_limit currency matches account currency (if provided)
      Raises: InvalidCardDataError

  // Updates
  + update_name(card_name: str) -> None
      Validates: non-empty
      Updates: card_name, updated_at

  + update_network(card_network: CardNetwork?) -> None
      Updates: card_network, updated_at

  + update_expiry(month: int, year: int) -> None
      Validates: month 1-12
      Updates: expiry_month, expiry_year, updated_at

  + update_credit_limit(credit_limit: Money?) -> None
      Validates: positive if provided, currency matches account
      Updates: credit_limit, updated_at
      Raises: InvalidCreditLimitError, CurrencyMismatchError

  + update_issuing_institution(institution_id: UUID?) -> None
      Updates: issuing_institution_id, updated_at

  + update_notes(notes: str?) -> None
      Updates: notes, updated_at

  // Lifecycle
  + soft_delete(deleted_by: UUID) -> None
      Validates: not already deleted
      Sets: deleted_at
      Emits: CardSoftDeleted
      Raises: AlreadyDeletedError
      Note: Does NOT affect transactions linked to this card
            (card_id on transactions is preserved for history)

  + recover() -> None
      Validates: is deleted, parent account is active
      Clears: deleted_at
      Emits: CardRecovered
      Raises: NotDeletedError, ParentDeletedError
```

## 5. Account Aggregate — Card Operations

Cards are managed through the Account aggregate:

```
Account:
  // Add card
  + add_card(card: Card) -> None
      Validates:
        1. Account is active
           Raises: AccountNotActiveError
        2. Card's account_id matches this account
        3. If credit_limit provided, currency matches account currency
           Raises: CurrencyMismatchError
      Effect: Card added to account's card collection
      Emits: CardCreated

  // Remove card
  + remove_card(card_id: UUID, removed_by: UUID) -> None
      Validates:
        1. Card exists and belongs to this account
           Raises: CardNotFoundError
        2. Card is not already deleted
      Effect: Soft deletes the card
      Emits: CardSoftDeleted
      Note: Transactions referencing this card retain the card_id

  // Recover card
  + recover_card(card_id: UUID) -> None
      Validates:
        1. Card exists, belongs to this account, and is deleted
        2. Account is active
      Effect: Recovers the card
      Emits: CardRecovered

  // Query
  + get_cards(include_deleted: bool = False) -> list[Card]
      Returns: cards for this account

  + get_card_by_id(card_id: UUID) -> Card?
      Returns: card if exists and belongs to this account
```

## 6. Card-Transaction Linking

Transactions can optionally reference a card via `card_id` (defined in Spec 009). This section specifies the linking behavior.

### 6.1 Linking Rules

| Rule | Description |
|------|-------------|
| Optional | `card_id` on a transaction is nullable — not all transactions use a card |
| Same account | The referenced card must belong to the same account as the transaction |
| Deleted cards | A transaction can reference a deleted card (historical record preserved) |
| No cascade | Deleting a card does NOT null out `card_id` on linked transactions |
| Reassignment | `card_id` on a transaction can be changed (mutable field) |

### 6.2 Linking Operations

```
Account:
  + link_transaction_to_card(transaction_id: UUID, card_id: UUID) -> None
      Validates:
        1. Transaction exists in this account and is active
        2. Card exists in this account (may be deleted — historical linking ok)
      Effect: Sets transaction.card_id = card_id
      Emits: TransactionCardLinked

  + unlink_transaction_from_card(transaction_id: UUID) -> None
      Validates:
        1. Transaction exists in this account and is active
        2. Transaction has a card_id set
      Effect: Sets transaction.card_id = None
      Emits: TransactionCardUnlinked
```

### 6.3 Card Usage Query

```
Account:
  + get_transactions_by_card(
      card_id: UUID,
      date_range: DateRange? = None,
      include_deleted: bool = False
    ) -> list[Transaction]
      Returns: transactions linked to the specified card
```

## 7. Validation Rules

| Rule ID | Rule | Enforcement |
|---------|------|-------------|
| CRD-001 | Card must belong to an account | Card.account_id is required and immutable |
| CRD-002 | Last four digits exactly 4 numeric characters | CardLastFour value object |
| CRD-003 | Expiry month 1-12 | Card.create() and Card.update_expiry() |
| CRD-004 | Credit limit positive if specified | Card.create() and Card.update_credit_limit() |

## 8. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `CardCreated` | `account.add_card()` | card_id, account_id, card_type, last_four |
| `CardUpdated` | Any card update method | card_id, changed_fields |
| `CardSoftDeleted` | `account.remove_card()` | card_id, account_id, deleted_by |
| `CardRecovered` | `account.recover_card()` | card_id, account_id |
| `TransactionCardLinked` | `link_transaction_to_card()` | transaction_id, card_id |
| `TransactionCardUnlinked` | `unlink_transaction_from_card()` | transaction_id, old_card_id |

## 9. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `InvalidCardLastFourError` | CardLastFour construction | Not exactly 4 numeric digits |
| `InvalidCardDataError` | Card.create() validation | Invalid expiry month, empty name, etc. |
| `InvalidCreditLimitError` | Negative or zero credit limit | Credit limit must be positive |
| `CardNotFoundError` | Operation on non-existent card | Card doesn't exist in account |

## 10. Repository Interface

```
CardRepository (Protocol):
  + save(card: Card) -> None
  + find_by_id(card_id: UUID) -> Card?
  + find_by_account(account_id: UUID, include_deleted: bool = False) -> list[Card]
```

## 11. Acceptance Criteria

### Card Creation

- [ ] Card created with valid attributes succeeds
- [ ] Card requires non-empty `card_name`
- [ ] `last_four_digits` must be exactly 4 numeric characters
- [ ] `expiry_month` must be 1-12 — raises `InvalidCardDataError` otherwise
- [ ] `credit_limit` must be positive if provided — raises `InvalidCreditLimitError` if zero/negative
- [ ] `credit_limit` currency must match account currency
- [ ] Card on deleted account raises `AccountNotActiveError`
- [ ] `CardCreated` event emitted

### Immutable Fields

- [ ] `card_type` cannot be changed after creation
- [ ] `last_four_digits` cannot be changed after creation
- [ ] `account_id` cannot be changed after creation

### Card Updates

- [ ] `card_name`, `card_network`, `expiry_month/year`, `credit_limit`, `notes` can be updated
- [ ] `updated_at` set on every update
- [ ] `CardUpdated` event emitted

### Card-Transaction Linking

- [ ] Transaction can be linked to a card in the same account
- [ ] Transaction can be linked to a deleted card (historical reference)
- [ ] Transaction `card_id` can be changed to a different card
- [ ] Transaction `card_id` can be cleared (unlinked)
- [ ] Card and transaction must be in the same account
- [ ] `TransactionCardLinked` / `TransactionCardUnlinked` events emitted

### Lifecycle

- [ ] Soft deleting a card does NOT affect linked transactions (`card_id` preserved)
- [ ] Soft deleting a card sets `deleted_at`
- [ ] Recovering a card requires parent account to be active
- [ ] Soft deleted cards excluded from card listings by default
- [ ] Soft deleted cards included with `include_deleted=True`

### Authorization

- [ ] Managing cards (add, update, remove) requires EDITOR permission
- [ ] Viewing cards requires VIEWER permission
- [ ] Recovering cards requires OWNER permission

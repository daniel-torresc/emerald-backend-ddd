# Spec 017: Multi-Currency Support

**Status:** Draft
**Bounded Context:** Cross-Cutting
**Dependencies:** 001 (Shared Kernel)
**Blocks:** None

---

## 1. Overview

This spec defines how the Emerald Finance Platform handles multiple currencies — from per-account native currency enforcement to cross-account reporting in a user's preferred display currency. Accounts are single-currency (immutable after creation), but users can have accounts in different currencies and see consolidated views with conversion.

**Key Principle:** Actual monetary amounts are never converted in storage. Currency conversion is for **display only**. Each account operates in a single currency, and all transactions within it must match. Conversion happens at the reporting/display layer using the latest exchange rates.

## 2. Scope

### In Scope

- Currency master data management
- Exchange rate sourcing and storage
- Display conversion for consolidated views
- Net worth calculation across currencies
- User's preferred display currency (from UserPreferences)
- Currency formatting rules
- Exchange rate service interface

### Out of Scope

- Foreign exchange transactions (buying/selling currency)
- Historical exchange rate storage (only current rates)
- Currency conversion within a single account (impossible — currency is immutable)
- Cryptocurrency support (future consideration)

## 3. Currency Master Data

### 3.1 Currency Entity (Master Data)

Currencies are managed as master data by admins. The `Currency` value object (Spec 001) is constructed from this master data.

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| currency_id | UUID | No | Unique identifier |
| code | str | No | ISO 4217 code (e.g., "USD") |
| symbol | str | Yes | Display symbol (e.g., "$", "EUR") |
| name | str | Yes | Full name (e.g., "US Dollar") |
| decimal_places | int | No | Number of decimal places (e.g., 2 for USD, 0 for JPY) |
| is_active | bool | Yes | Whether available for new accounts |
| sort_order | int | Yes | Display order in currency pickers |

### 3.2 Core Currency Set

The platform ships with a default set of currencies. Admins can add more or deactivate unused ones.

| Code | Symbol | Name | Decimals |
|------|--------|------|----------|
| USD | $ | US Dollar | 2 |
| EUR | EUR | Euro | 2 |
| GBP | £ | British Pound | 2 |
| JPY | ¥ | Japanese Yen | 0 |
| CHF | CHF | Swiss Franc | 2 |
| CAD | CA$ | Canadian Dollar | 2 |
| AUD | A$ | Australian Dollar | 2 |
| CNY | ¥ | Chinese Yuan | 2 |
| INR | ₹ | Indian Rupee | 2 |
| MXN | MX$ | Mexican Peso | 2 |
| BRL | R$ | Brazilian Real | 2 |

**Rules:**
- Currency code must be valid ISO 4217 (3 uppercase letters)
- Currency code is immutable after creation
- Deactivating a currency does not affect existing accounts using it
- `decimal_places` is immutable (fundamental to the currency)

## 4. Exchange Rates

### 4.1 Exchange Rate Model

Exchange rates are stored as a base-currency-relative table, updated periodically from external sources.

**ExchangeRate Value Object:**

| Attribute | Type | Description |
|-----------|------|-------------|
| base_currency | str | Base currency code (e.g., "EUR") |
| target_currency | str | Target currency code (e.g., "USD") |
| rate | Decimal | How many target units per 1 base unit |
| effective_at | datetime | When this rate was published |
| source | str | Where the rate came from (e.g., "ECB") |

**Example:**

```
base=EUR, target=USD, rate=1.0852
→ 1 EUR = 1.0852 USD
```

### 4.2 Exchange Rate Storage

| Rule | Description |
|------|-------------|
| Current rates only | Only the latest rates are stored (not historical) |
| Base currency | All rates stored relative to a single base (e.g., EUR from ECB) |
| Update frequency | Minimum daily, configurable |
| Staleness threshold | Rates older than 48 hours trigger a warning |
| Source | Official APIs (ECB, etc.) |

### 4.3 Rate Conversion Logic

```
CurrencyConverter:
  + convert(
      amount: Money,
      target_currency: Currency,
      rates: ExchangeRateSet
    ) -> ConvertedMoney
      1. If amount.currency == target_currency:
         Return as-is (no conversion)
      2. Find rate from amount.currency to target_currency:
         a. Direct rate exists → use it
         b. No direct rate → triangulate via base currency
      3. converted_amount = amount.amount * rate
      4. Round to target_currency.decimal_places
      5. Return ConvertedMoney(amount, target_currency, rate_used, converted_at)
```

**Triangulation:**

```
Convert GBP → JPY when only EUR-based rates exist:
  1. GBP → EUR: 1 / rate(EUR→GBP)
  2. EUR → JPY: rate(EUR→JPY)
  3. GBP → JPY: step1 * step2
```

### 4.4 ConvertedMoney (Value Object)

Represents a display-only converted amount. Distinct from `Money` to make clear this is an approximation.

| Attribute | Type | Description |
|-----------|------|-------------|
| original | Money | The unconverted original amount |
| converted_amount | Decimal | Amount in target currency |
| target_currency | Currency | Currency converted to |
| rate_used | Decimal | Exchange rate applied |
| converted_at | datetime | When conversion was performed |

**Rules:**

- `ConvertedMoney` is **not** usable in arithmetic operations
- `ConvertedMoney` is for display only — it cannot be persisted as a transaction amount
- Must always show the user that this is a converted value (not actual)

## 5. Display Currency

### 5.1 User Preference

Each user has a `display_currency` in their preferences (Spec 002, `UserPreferences`). This determines:

| Use Case | Behavior |
|----------|----------|
| Net worth total | Sum of all account balances converted to display currency |
| Cross-account reports | All amounts shown in display currency |
| Single account view | Native currency (no conversion) |
| Transaction list | Native currency (no conversion) |
| Dashboard totals | Display currency |

### 5.2 Conversion Indicators

When amounts are displayed in a converted currency, the UI must clearly indicate:

| Indicator | Description |
|-----------|-------------|
| Conversion symbol | Visual marker that this is a converted amount (e.g., "~" prefix) |
| Native amount | Original amount in native currency always accessible |
| Rate timestamp | When the exchange rate was fetched |
| Staleness warning | Alert if rate is older than threshold |

## 6. Multi-Currency Reporting

### 6.1 Net Worth Calculation

```
NetWorthService:
  + calculate_net_worth(
      user_id: UUID,
      display_currency: Currency
    ) -> NetWorthSummary

  NetWorthSummary:
    - total: ConvertedMoney           (sum in display currency)
    - accounts: list[AccountBalance]  (each account's contribution)
    - rates_as_of: datetime           (when rates were fetched)
    - is_stale: bool                  (any rate older than threshold)

  AccountBalance:
    - account_id: UUID
    - account_name: str
    - native_balance: Money           (actual balance in account currency)
    - converted_balance: ConvertedMoney  (converted to display currency)
```

**Calculation:**

```
For each accessible account:
  1. Calculate native balance (Spec 007: opening_balance + Σ transactions)
  2. Convert to display currency using latest rate
  3. Sum all converted balances

Total net worth = Σ(converted_balances)
```

### 6.2 Spending by Category (Cross-Currency)

```
For category "Food" across accounts in USD, EUR, GBP:
  1. Sum transactions by category per account (native currency)
  2. Convert each sum to display currency
  3. Total = Σ(converted sums)
  4. Always show breakdown by native currency alongside
```

### 6.3 Same-Currency Aggregation

When all accounts use the same currency, no conversion is needed — amounts are directly summed. The system should detect this case and skip the conversion layer for accuracy.

```
if all account currencies == display_currency:
    total = Σ(native_balances)  # exact, no conversion
else:
    total = Σ(converted_balances)  # approximate
```

## 7. Currency Operations on Money (Spec 001 Extension)

The `Money` value object (Spec 001) enforces single-currency operations. This spec clarifies the cross-currency interaction rules:

| Operation | Same Currency | Different Currency |
|-----------|--------------|-------------------|
| Addition | Direct arithmetic | `CurrencyMismatchError` |
| Subtraction | Direct arithmetic | `CurrencyMismatchError` |
| Comparison | Direct comparison | `CurrencyMismatchError` |
| Display conversion | N/A (already in target) | Via `CurrencyConverter` → `ConvertedMoney` |

**Key Rule:** `Money` objects of different currencies can NEVER be directly combined. Conversion must be explicit, producing a `ConvertedMoney` display value — not a `Money` value that could be confused with an actual amount.

## 8. Exchange Rate Service Interface

```
ExchangeRateProvider (Protocol):
  + fetch_latest_rates(base_currency: str) -> list[ExchangeRate]
      Fetches current rates from external API
      Returns: rates relative to base_currency

ExchangeRateRepository (Protocol):
  + save_rates(rates: list[ExchangeRate]) -> None
      Replaces current rates with new set
  + get_current_rates() -> ExchangeRateSet
      Returns all current rates
  + get_rate(base: str, target: str) -> ExchangeRate?
      Returns specific rate pair
  + get_rates_age() -> datetime
      Returns effective_at of current rate set

ExchangeRateSet:
  - rates: dict[tuple[str, str], ExchangeRate]
  - effective_at: datetime
  - source: str

  + get_rate(from_currency: str, to_currency: str) -> Decimal?
      Direct lookup, with triangulation fallback
  + is_stale(threshold: timedelta = timedelta(hours=48)) -> bool
```

## 9. Exchange Rate Update Service

```
ExchangeRateUpdateService:
  + update_rates() -> ExchangeRateUpdateResult
      1. Fetch latest rates from provider
      2. Validate rates (sanity check — no extreme changes)
      3. Store as current rates
      4. Emit ExchangeRatesUpdated event
      Returns: count of rates updated, any warnings

  Scheduled: runs daily (configurable, minimum daily)
```

**Sanity Checks:**

| Check | Description |
|-------|-------------|
| Rate > 0 | No zero or negative rates |
| Change threshold | Flag rates that changed > 10% from previous (for manual review) |
| Completeness | Warn if expected currencies are missing |

## 10. Currency Formatting

### 10.1 Formatting Rules

| Currency | Example (positive) | Example (negative) | Decimal Places |
|----------|-------------------|--------------------| --------------|
| USD | $1,234.56 | -$1,234.56 | 2 |
| EUR | EUR 1.234,56 | -EUR 1.234,56 | 2 |
| GBP | £1,234.56 | -£1,234.56 | 2 |
| JPY | ¥1,235 | -¥1,235 | 0 |

**Rules:**

- Formatting follows user's locale preference (from `UserPreferences`)
- Symbol placement (prefix/suffix) is locale-dependent
- Thousand separator and decimal separator are locale-dependent
- Rounding uses currency's `decimal_places`

### 10.2 Formatting Service

```
CurrencyFormatter:
  + format(money: Money, locale: str) -> str
      Formats amount with currency symbol and locale-specific separators

  + format_converted(converted: ConvertedMoney, locale: str) -> str
      Same as format but with conversion indicator (e.g., "~$1,234.56")
```

## 11. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `ExchangeRatesUpdated` | Rate update service | source, rate_count, effective_at |
| `ExchangeRatesStale` | Staleness check | last_update, threshold |

## 12. Acceptance Criteria

### Currency Master Data

- [ ] Core currency set (USD, EUR, GBP, JPY, etc.) available on platform setup
- [ ] Admin can add new currencies with valid ISO 4217 codes
- [ ] Admin can deactivate currencies (existing accounts unaffected)
- [ ] Currency code and decimal_places are immutable
- [ ] Deactivated currencies not shown in currency pickers for new accounts

### Exchange Rates

- [ ] Rates fetched from external provider (ECB or equivalent)
- [ ] Rates updated at least daily
- [ ] Only latest rates stored (no historical rates)
- [ ] Rates older than 48 hours flagged as stale
- [ ] Sanity checks flag rates with >10% change
- [ ] `ExchangeRatesUpdated` event emitted after successful update

### Currency Conversion

- [ ] Same-currency conversion returns original value unchanged
- [ ] Direct rate used when available
- [ ] Triangulation via base currency when no direct rate exists
- [ ] Converted amounts rounded to target currency's decimal places
- [ ] `ConvertedMoney` is distinct from `Money` (cannot be used in arithmetic)
- [ ] `ConvertedMoney` carries the rate used and conversion timestamp

### Display Currency

- [ ] User's preferred display currency used for consolidated views
- [ ] Net worth calculated as sum of all account balances converted to display currency
- [ ] Single account views show native currency (no conversion)
- [ ] Transaction lists show native currency (no conversion)
- [ ] Converted amounts clearly indicated as approximate

### Net Worth

- [ ] Net worth sums all accessible accounts' balances in display currency
- [ ] Each account shows both native and converted balance
- [ ] Staleness indicator shown when rates are outdated
- [ ] When all accounts share the same currency as display, exact sum used (no conversion)

### Currency Formatting

- [ ] Amounts formatted according to user's locale preference
- [ ] Currency symbol, thousand separator, decimal separator are locale-specific
- [ ] Rounding follows currency's decimal_places
- [ ] Converted amounts prefixed with approximation indicator

### Money Value Object Enforcement

- [ ] Adding Money of different currencies raises `CurrencyMismatchError`
- [ ] Comparing Money of different currencies raises `CurrencyMismatchError`
- [ ] No implicit currency conversion anywhere in domain logic

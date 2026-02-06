# Spec 018: Search & Filtering

**Status:** Draft
**Bounded Context:** Cross-Cutting
**Dependencies:** 009 (Transaction Management)
**Blocks:** None

---

## 1. Overview

This spec defines the search and filtering capabilities for transactions across all of a user's accessible accounts. It covers structured filtering (date range, amount, categories, etc.), full-text search (descriptions, merchants, comments), and result sorting and pagination. Search is a read-only query concern that spans the Core Finance and Classification contexts.

**Key Principle:** Search operates within the user's authorization boundary — results only include transactions from accounts where the user has at least VIEWER permission. Search never bypasses domain authorization.

## 2. Scope

### In Scope

- Transaction search across multiple accounts
- Structured filters (date, amount, account, category, merchant, etc.)
- Full-text search across descriptions, merchants, and comments
- Fuzzy matching for typos
- Result sorting (date, amount, description, etc.)
- Pagination
- Search within deleted items (trash search)
- Search suggestions based on history

### Out of Scope

- Account search (accounts are few enough to list directly)
- Taxonomy/term search (separate, simpler concern)
- Search indexing infrastructure (implementation detail)
- Saved searches / search presets (future enhancement)

## 3. Transaction Search Criteria

### 3.1 TransactionSearchQuery

| Filter | Type | Description |
|--------|------|-------------|
| text_query | str? | Free-text search across descriptions, merchants, comments |
| date_range | DateRange? | Transactions within date range |
| amount_min | Decimal? | Minimum amount (inclusive) |
| amount_max | Decimal? | Maximum amount (inclusive) |
| account_ids | list[UUID]? | Specific accounts (None = all accessible) |
| review_status | ReviewStatus? | TO_REVIEW or REVIEWED |
| has_category | bool? | True = categorized, False = uncategorized, None = both |
| category_term_ids | list[UUID]? | Specific taxonomy terms (includes descendants) |
| taxonomy_id | UUID? | Filter by taxonomy (used with has_category) |
| merchants | list[str]? | Specific merchant names |
| card_ids | list[UUID]? | Specific cards used |
| import_source_type | ImportSourceType? | Manual, BankImport, BulkImport, API |
| include_deleted | bool | Include soft-deleted transactions (default: False) |
| include_split_children | bool | Include split child transactions (default: True) |
| exclude_split_parents | bool | Exclude split parents that have children (default: False) |

### 3.2 Filter Combinations

All filters are combined with AND logic. Within list-type filters (account_ids, merchants, etc.), items are combined with OR logic.

```
Example: "Show me unreviewed food transactions over $50 from my checking account"

TransactionSearchQuery(
    account_ids=[checking_account_id],
    review_status=TO_REVIEW,
    category_term_ids=[food_term_id],   # includes "Food" and all descendants
    amount_min=Decimal("-50.00"),        # note: debits are negative
    amount_max=Decimal("-0.01"),         # exclude zero and positive
)
```

### 3.3 Amount Filtering Semantics

Since transactions use signed amounts (positive = credit, negative = debit):

| Filter Intent | amount_min | amount_max |
|---------------|-----------|-----------|
| All debits over $50 | None | -50.00 |
| All credits over $100 | 100.00 | None |
| All transactions between -$50 and $50 | -50.00 | 50.00 |
| Exact amount $25.00 | 25.00 | 25.00 |

**Note:** `amount_min` and `amount_max` operate on the signed amount value. The application/presentation layer may provide user-friendly "debit amount" and "credit amount" filters that translate to the signed range.

## 4. Full-Text Search

### 4.1 Searchable Fields

| Field | Weight | Description |
|-------|--------|-------------|
| user_description | High | User's custom description (if set) |
| original_description | High | Original import/creation description |
| merchant | High | Merchant name |
| comments | Medium | User notes |

**Search Order:** When `text_query` is provided, results are ranked by relevance. When no `text_query` is provided, results use the specified sort order.

### 4.2 Search Features

| Feature | Description |
|---------|-------------|
| Tokenized matching | Query "coffee shop" matches "Coffee Shop Downtown" |
| Case-insensitive | "amazon" matches "Amazon" |
| Prefix matching | "amaz" matches "Amazon" |
| Fuzzy matching | "amazn" matches "Amazon" (1 edit distance) |
| Phrase matching | `"coffee shop"` (quoted) matches exact phrase |
| Effective description | Search uses `user_description` if set, falls back to `original_description` |

### 4.3 Fuzzy Matching Rules

| Edit Distance | Behavior |
|---------------|----------|
| 0 | Exact match (highest relevance) |
| 1 | One character difference (high relevance) |
| 2 | Two character differences (medium relevance, for words > 5 chars) |

**Rules:**
- Fuzzy matching only applies to words with 4+ characters
- Short words (1-3 chars) require exact match
- Maximum edit distance scales with word length (1 for 4-6 chars, 2 for 7+ chars)

## 5. Sorting

### 5.1 Sort Options

| Sort Field | Description | Default Direction |
|------------|-------------|-------------------|
| transaction_date | When transaction occurred | Descending (newest first) |
| amount | Transaction amount | Descending (largest first) |
| description | Effective description (alphabetical) | Ascending |
| merchant | Merchant name (alphabetical) | Ascending |
| created_at | When created in platform | Descending |
| relevance | Full-text search relevance score | Descending |

### 5.2 Sort Rules

- Default sort: `transaction_date DESC, created_at DESC`
- When `text_query` is provided and no explicit sort: `relevance DESC`
- Secondary sort is always `created_at DESC` (stable ordering for ties)
- Null values sort last (e.g., transactions without merchant)

## 6. Pagination

### 6.1 PaginatedResult

| Attribute | Type | Description |
|-----------|------|-------------|
| items | list[TransactionSearchResult] | Results for current page |
| total_count | int | Total matching results |
| page | int | Current page number (1-based) |
| page_size | int | Items per page |
| total_pages | int | Total pages |
| has_next | bool | Whether more pages exist |
| has_previous | bool | Whether previous pages exist |

### 6.2 Pagination Rules

| Setting | Default | Maximum |
|---------|---------|---------|
| page_size | 20 | 100 |
| page | 1 | total_pages |

## 7. Search Result

### 7.1 TransactionSearchResult

| Attribute | Type | Description |
|-----------|------|-------------|
| transaction_id | UUID | Transaction identifier |
| account_id | UUID | Account it belongs to |
| account_name | str | Account display name |
| transaction_date | date | When transaction occurred |
| amount | Money | Transaction amount (native currency) |
| effective_description | str | user_description or original_description |
| merchant | str? | Merchant name |
| review_status | ReviewStatus | TO_REVIEW or REVIEWED |
| categories | list[CategorySummary] | Assigned terms (from all taxonomies) |
| card_name | str? | Card display name (if linked) |
| is_split_parent | bool | Whether this is a split parent |
| is_split_child | bool | Whether this is a split child |
| import_source_type | ImportSourceType? | How it was created |
| is_deleted | bool | Whether soft deleted (for trash search) |
| relevance_score | float? | Full-text relevance (when text_query used) |

**CategorySummary:**

| Attribute | Type | Description |
|-----------|------|-------------|
| taxonomy_name | str | Taxonomy the term belongs to |
| term_name | str | Term display name |
| term_path | str | Full path (e.g., "Food > Restaurants") |

### 7.2 Search Aggregations

Along with results, search can return summary aggregations:

```
TransactionSearchAggregations:
  - total_credit: Money?       (sum of positive amounts, per-currency)
  - total_debit: Money?        (sum of negative amounts, per-currency)
  - net_total: Money?           (sum of all amounts, per-currency)
  - count_by_review_status: dict[ReviewStatus, int]
  - count_by_category: list[CategoryCount]

CategoryCount:
  - term_id: UUID
  - term_name: str
  - count: int
```

**Note:** Aggregations are per-currency when the search spans multiple currencies. For single-currency results, they are straightforward sums.

## 8. Category-Based Filtering

### 8.1 Hierarchical Term Matching

When filtering by `category_term_ids`, the search includes transactions categorized with the specified terms **and all their descendants**.

```
Filter by term "Food":
  Matches: "Food", "Food > Groceries", "Food > Restaurants",
           "Food > Restaurants > Italian", etc.

Implementation:
  1. For each term_id in category_term_ids:
     a. Get term and all descendant term_ids
     b. Add to expanded term set
  2. Match transactions with any term in expanded set
```

### 8.2 Uncategorized Filter

When `has_category = False` and `taxonomy_id` is provided:

```
Find transactions that have NO assignment in the specified taxonomy.
Used for: "Show me transactions I haven't categorized yet"
```

When `has_category = False` and `taxonomy_id` is None:

```
Find transactions that have NO assignments in ANY taxonomy.
Used for: "Show me completely uncategorized transactions"
```

## 9. Authorization

### 9.1 Search Scope

Search results are **always** scoped to the user's authorized accounts:

```
SearchService:
  1. Get all account_ids where user has at least VIEWER permission
  2. If account_ids filter provided:
     Intersect with authorized account_ids
     (user cannot search accounts they don't have access to)
  3. Execute search within authorized scope
```

### 9.2 Deleted Transaction Visibility

| User Permission | include_deleted=False | include_deleted=True |
|-----------------|----------------------|---------------------|
| OWNER | Active only | Active + deleted |
| EDITOR | Active only | Active + deleted (own only) |
| VIEWER | Active only | Not allowed (VIEWER can't see trash) |

## 10. Search Suggestions

### 10.1 Merchant Suggestions

```
SearchSuggestionService:
  + suggest_merchants(
      user_id: UUID,
      prefix: str,
      limit: int = 10
    ) -> list[str]
      Returns merchant names matching prefix from user's transactions
      Ordered by frequency (most used first)
```

### 10.2 Description Suggestions

```
SearchSuggestionService:
  + suggest_descriptions(
      user_id: UUID,
      prefix: str,
      limit: int = 10
    ) -> list[str]
      Returns descriptions matching prefix
      Ordered by recency (most recent first)
```

## 11. Search Service Interface

```
TransactionSearchService (Protocol):
  + search(
      user_id: UUID,
      query: TransactionSearchQuery,
      sort_by: str = "transaction_date",
      sort_order: str = "desc",
      page: int = 1,
      page_size: int = 20,
      include_aggregations: bool = False
    ) -> TransactionSearchResponse

TransactionSearchResponse:
  - results: PaginatedResult[TransactionSearchResult]
  - aggregations: TransactionSearchAggregations?  (if requested)
  - query_time_ms: int  (for performance monitoring)
```

## 12. Acceptance Criteria

### Structured Filtering

- [ ] Filter by date range returns transactions within inclusive bounds
- [ ] Filter by amount range operates on signed values correctly
- [ ] Filter by specific accounts returns only those accounts' transactions
- [ ] Filter by review status (TO_REVIEW / REVIEWED) works correctly
- [ ] Filter by category term includes descendants (hierarchical matching)
- [ ] Filter by `has_category=False` finds uncategorized transactions
- [ ] Filter by merchant matches exact merchant names
- [ ] Filter by card returns transactions linked to specific cards
- [ ] Filter by import source type works correctly
- [ ] All filters combine with AND logic
- [ ] Within list filters, items combine with OR logic

### Full-Text Search

- [ ] Text query searches across user_description, original_description, merchant, comments
- [ ] Search is case-insensitive
- [ ] Search supports prefix matching ("amaz" → "Amazon")
- [ ] Search supports fuzzy matching ("amazn" → "Amazon") for words 4+ chars
- [ ] Quoted phrases match exactly
- [ ] Results ranked by relevance when text_query provided
- [ ] Effective description (user override or original) is used for matching

### Sorting & Pagination

- [ ] Default sort is transaction_date DESC
- [ ] When text_query provided, default sort is relevance DESC
- [ ] Secondary sort is always created_at DESC for stable ordering
- [ ] Pagination returns correct page_size, total_count, total_pages
- [ ] Default page_size is 20, maximum is 100
- [ ] has_next / has_previous flags are accurate

### Authorization

- [ ] Results only include transactions from accounts user has VIEWER+ access
- [ ] Account filter is intersected with authorized accounts (cannot search unauthorized)
- [ ] Deleted transactions visible to OWNER and EDITOR (own only) when include_deleted=True
- [ ] VIEWER cannot see deleted transactions even with include_deleted=True

### Search Results

- [ ] Each result includes account_name, effective_description, categories, card_name
- [ ] Split parent/child flags are set correctly
- [ ] Relevance score included when text_query was used
- [ ] Aggregations (credit/debit totals, category counts) returned when requested
- [ ] Aggregations respect per-currency grouping for multi-currency results

### Suggestions

- [ ] Merchant suggestions match by prefix, ordered by frequency
- [ ] Description suggestions match by prefix, ordered by recency
- [ ] Suggestions scoped to user's own transactions only

### Performance

- [ ] Search across all user accounts returns within 500ms (p95)
- [ ] Full-text search with fuzzy matching returns within 500ms (p95)

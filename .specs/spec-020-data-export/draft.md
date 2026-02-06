# Spec 020: Data Export

**Status:** Draft
**Bounded Context:** Cross-Cutting
**Dependencies:** 009 (Transaction Management)
**Blocks:** None

---

## 1. Overview

This spec defines the data export capabilities of the Emerald Finance Platform — allowing users to extract their financial data in multiple formats for external use, regulatory compliance, and data portability. Exports support scoped extraction (specific accounts, date ranges, entity types) and full data portability (GDPR).

**Key Principle:** Users own their data. They must be able to export all their financial data in standard, portable formats at any time. Exports respect authorization boundaries — users can only export data from accounts they have access to.

## 2. Scope

### In Scope

- Export formats: CSV, JSON, PDF, OFX/QFX
- Export scopes: full data, per-account, date range, entity type
- GDPR data portability (full export of all user data)
- Asynchronous export for large datasets
- Export job lifecycle (requested → processing → ready → expired)
- Download management (temporary secure URLs)

### Out of Scope

- Report generation with charts and analytics (future — Phase 2 Intelligence)
- Scheduled/recurring exports (future enhancement)
- Direct export to third-party services (future)
- Import from exported files (separate concern)

## 3. Export Formats

### 3.1 CSV

| Aspect | Detail |
|--------|--------|
| Use case | Spreadsheet analysis, accounting software import |
| Encoding | UTF-8 with BOM (for Excel compatibility) |
| Delimiter | Comma (configurable to semicolon for locales using comma as decimal) |
| Headers | First row contains column names |
| Date format | ISO 8601 (YYYY-MM-DD) |
| Amount format | Plain decimal, no currency symbol (e.g., "-45.50") |
| Currency column | Separate column for currency code |

**Transaction CSV Columns:**

| Column | Description |
|--------|-------------|
| transaction_date | Date of transaction |
| value_date | Settlement date |
| amount | Signed decimal amount |
| currency | ISO 4217 currency code |
| description | Effective description (user override or original) |
| original_description | Original import description |
| merchant | Merchant name |
| category | Primary category path (e.g., "Food > Restaurants") |
| review_status | TO_REVIEW or REVIEWED |
| account_name | Account display name |
| card_name | Card used (if any) |
| import_source | Manual, BankImport, etc. |
| comments | User notes |
| created_at | When created in platform |

**Account CSV Columns:**

| Column | Description |
|--------|-------------|
| account_name | Display name |
| account_type | Account type name |
| institution | Financial institution name |
| currency | ISO 4217 code |
| opening_balance | Initial balance |
| current_balance | Calculated balance |
| iban | Masked IBAN (if set) |
| created_at | When created |

### 3.2 JSON

| Aspect | Detail |
|--------|--------|
| Use case | Data portability, API integration, backup |
| Encoding | UTF-8 |
| Structure | Hierarchical (accounts contain transactions) |
| Date format | ISO 8601 with timezone |
| Amount format | String decimal (avoids floating-point issues) |

**JSON Structure:**

```json
{
  "export_metadata": {
    "exported_at": "2026-02-05T12:00:00Z",
    "exported_by": "user_id",
    "format_version": "1.0",
    "scope": "full" | "account" | "date_range"
  },
  "accounts": [
    {
      "account_id": "...",
      "account_name": "Checking",
      "currency": "USD",
      "opening_balance": "1000.00",
      "current_balance": "2450.75",
      "transactions": [
        {
          "transaction_id": "...",
          "transaction_date": "2026-01-15",
          "amount": "-45.50",
          "currency": "USD",
          "description": "Coffee Shop",
          "original_description": "POS COFFEE SHOP #123",
          "merchant": "Coffee Shop",
          "categories": [
            {"taxonomy": "Categories", "term": "Food > Coffee"}
          ],
          "review_status": "REVIEWED",
          "comments": null,
          "import_source": "BANK_IMPORT"
        }
      ],
      "cards": [
        {
          "card_id": "...",
          "card_name": "Personal Visa",
          "card_type": "DEBIT",
          "last_four": "4521",
          "network": "VISA"
        }
      ]
    }
  ],
  "taxonomies": [
    {
      "taxonomy_id": "...",
      "name": "Categories",
      "terms": [
        {"term_id": "...", "name": "Food", "parent": null},
        {"term_id": "...", "name": "Coffee", "parent": "Food"}
      ]
    }
  ]
}
```

### 3.3 PDF

| Aspect | Detail |
|--------|--------|
| Use case | Account statements, printable reports |
| Layout | Formatted with headers, tables, totals |
| Content | Account summary + transaction listing |
| Branding | Platform name and export date in header/footer |

**PDF Content:**

```
┌─────────────────────────────────────────┐
│  Emerald Finance - Account Statement    │
│  Generated: 2026-02-05                  │
├─────────────────────────────────────────┤
│                                         │
│  Account: Checking (USD)                │
│  Period: Jan 1 - Jan 31, 2026           │
│  Opening Balance: $1,000.00             │
│  Closing Balance: $2,450.75             │
│                                         │
│  ┌───────┬────────────────┬──────────┐  │
│  │ Date  │ Description    │  Amount  │  │
│  ├───────┼────────────────┼──────────┤  │
│  │ 01/15 │ Coffee Shop    │  -$45.50 │  │
│  │ 01/16 │ Salary Deposit │+$2,000.00│  │
│  │ ...   │ ...            │ ...      │  │
│  └───────┴────────────────┴──────────┘  │
│                                         │
│  Summary:                               │
│    Total Credits:  +$3,200.00           │
│    Total Debits:   -$1,749.25           │
│    Net Change:     +$1,450.75           │
│                                         │
└─────────────────────────────────────────┘
```

### 3.4 OFX/QFX

| Aspect | Detail |
|--------|--------|
| Use case | Import into financial software (Quicken, GnuCash, etc.) |
| Standard | Open Financial Exchange (OFX) 2.2 |
| Content | Transaction data in OFX XML format |
| Scope | Per-account only (OFX is account-centric) |

## 4. Export Scopes

### 4.1 ExportScope

| Scope | Description | Available Formats |
|-------|-------------|-------------------|
| FULL_DATA | All user data (GDPR portability) | JSON |
| ACCOUNT | Specific account(s) | CSV, JSON, PDF, OFX |
| DATE_RANGE | Transactions in date range | CSV, JSON, PDF |
| ENTITY_TYPE | Specific entity types only | JSON |

### 4.2 ExportRequest

| Attribute | Type | Description |
|-----------|------|-------------|
| request_id | UUID | Unique export request ID |
| user_id | UUID | Who requested the export |
| format | ExportFormat | CSV, JSON, PDF, OFX |
| scope | ExportScope | FULL_DATA, ACCOUNT, DATE_RANGE, ENTITY_TYPE |
| account_ids | list[UUID]? | Specific accounts (for ACCOUNT scope) |
| date_range | DateRange? | Date filter (for DATE_RANGE scope) |
| entity_types | list[str]? | Entity types (for ENTITY_TYPE scope) |
| include_deleted | bool | Include soft-deleted items (default: False) |
| requested_at | datetime | When requested |

### 4.3 Scope Validation

| Rule | Description |
|------|-------------|
| Authorization | Can only export from accounts with VIEWER+ permission |
| FULL_DATA format | Only JSON supports FULL_DATA scope |
| OFX scope | OFX only supports ACCOUNT scope (single account) |
| Account filter | account_ids intersected with authorized accounts |

## 5. Export Job Lifecycle

### 5.1 ExportJob Entity

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| job_id | UUID | No | Unique identifier |
| user_id | UUID | No | Who requested |
| request | ExportRequest | No | What was requested |
| status | ExportJobStatus | Yes | Current state |
| file_path | str? | Yes | Path to generated file |
| file_size_bytes | int? | Yes | Size of generated file |
| download_url | str? | Yes | Temporary secure download URL |
| download_expires_at | datetime? | Yes | When download URL expires |
| started_at | datetime? | Yes | When processing began |
| completed_at | datetime? | Yes | When processing finished |
| error_message | str? | Yes | If failed, why |
| created_at | datetime | No | When job was created |

### 5.2 ExportJobStatus

| Value | Description |
|-------|-------------|
| PENDING | Queued, waiting to be processed |
| PROCESSING | Currently generating export file |
| READY | File generated, available for download |
| DOWNLOADED | File has been downloaded at least once |
| EXPIRED | Download URL has expired, file cleaned up |
| FAILED | Export generation failed |

### 5.3 Job Lifecycle Flow

```
User requests export
     │
     ▼
┌──────────┐
│ PENDING  │  Job created, queued
└────┬─────┘
     │  Worker picks up job
     ▼
┌──────────────┐
│ PROCESSING   │  Generating file
└────┬─────┬───┘
     │     │
     │     └── Error → ┌──────────┐
     │                 │ FAILED   │
     │                 └──────────┘
     ▼
┌──────────┐
│  READY   │  File available, download URL generated
└────┬─────┘
     │  User downloads
     ▼
┌──────────────┐
│ DOWNLOADED   │  At least one download
└────┬─────────┘
     │  URL expires (24 hours)
     ▼
┌──────────┐
│ EXPIRED  │  File cleaned up
└──────────┘
```

### 5.4 Download Management

| Rule | Value | Description |
|------|-------|-------------|
| URL validity | 24 hours | Download URL expires after 24 hours |
| Max downloads | Unlimited | No limit within validity period |
| File retention | 24 hours after ready | File deleted when URL expires |
| Secure URL | Signed | URL contains signature to prevent guessing |
| HTTPS only | Required | Downloads only via HTTPS |

## 6. GDPR Data Portability

### 6.1 Full Data Export

GDPR Article 20 requires the ability to export all personal data in a structured, machine-readable format.

**Full export includes:**

| Data Category | Content |
|---------------|---------|
| User profile | Email, username, full_name, preferences |
| Accounts | All owned accounts with full details |
| Transactions | All transactions across all owned accounts |
| Cards | All cards |
| Categories | All taxonomies and terms |
| Shares | All account shares (given and received) |
| Bank connections | Connection metadata (no credentials) |
| Notification preferences | All preference settings |

**Excludes:**

| Data | Reason |
|------|--------|
| Password hashes | Security — never exported |
| Bank credentials | Security — never exported |
| Audit logs | Not personal data in the GDPR sense |
| Other users' data | Authorization boundary |

### 6.2 GDPR Export Rules

| Rule | Description |
|------|-------------|
| Format | JSON only (machine-readable, structured) |
| Completeness | All personal data the platform holds |
| Timeliness | Must be available within 30 days (target: < 1 hour) |
| Free of charge | No cost to the user |
| No credentials | Passwords, tokens, and bank credentials never included |

## 7. Export Service

```
DataExportService:
  + request_export(
      user_id: UUID,
      format: ExportFormat,
      scope: ExportScope,
      account_ids: list[UUID]? = None,
      date_range: DateRange? = None,
      entity_types: list[str]? = None,
      include_deleted: bool = False
    ) -> ExportJob
      1. Validate scope + format compatibility
      2. Validate authorization (account access)
      3. Create ExportJob (PENDING)
      4. Queue for async processing
      5. Return job with ID for polling
      Raises: InvalidExportScopeError, InsufficientPermissionError

  + get_job_status(job_id: UUID, user_id: UUID) -> ExportJob
      Returns current job state
      Raises: ExportJobNotFoundError

  + get_download_url(job_id: UUID, user_id: UUID) -> str
      Validates: job is READY or DOWNLOADED, URL not expired
      Returns: secure download URL
      Raises: ExportNotReadyError, ExportExpiredError

  + list_user_exports(
      user_id: UUID,
      page: int = 1,
      page_size: int = 10
    ) -> PaginatedResult[ExportJob]
      Returns: user's export history
```

### 7.1 Export Worker

```
ExportWorker:
  + process_job(job_id: UUID) -> None
      1. Load job, set status = PROCESSING
      2. Gather data based on scope (with authorization)
      3. Generate file in requested format
      4. Store file, generate signed download URL
      5. Set status = READY, file_path, download_url, download_expires_at
      6. Emit ExportCompleted event (triggers notification)

      On error:
      1. Set status = FAILED, error_message
      2. Emit ExportFailed event
```

### 7.2 Format Generators

```
ExportFormatGenerator (Protocol):
  + generate(data: ExportData, output_path: str) -> int
      Generates export file at output_path
      Returns: file size in bytes

CsvExportGenerator(ExportFormatGenerator)
JsonExportGenerator(ExportFormatGenerator)
PdfExportGenerator(ExportFormatGenerator)
OfxExportGenerator(ExportFormatGenerator)
```

## 8. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `ExportRequested` | Export job created | job_id, user_id, format, scope |
| `ExportCompleted` | File ready for download | job_id, user_id, file_size |
| `ExportFailed` | Generation error | job_id, user_id, error |
| `ExportDownloaded` | File downloaded | job_id, user_id |
| `ExportExpired` | Download URL expired | job_id |

## 9. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `InvalidExportScopeError` | Incompatible scope + format | e.g., FULL_DATA with CSV |
| `ExportJobNotFoundError` | Unknown job ID | Job doesn't exist or belongs to another user |
| `ExportNotReadyError` | Download before file ready | Job still PENDING or PROCESSING |
| `ExportExpiredError` | Download after URL expired | Must re-request export |
| `InsufficientPermissionError` | No access to requested accounts | Authorization failure |
| `ExportLimitExceededError` | Too many concurrent exports | Rate limit (max 3 active jobs) |

## 10. Repository Interfaces

```
ExportJobRepository (Protocol):
  + save(job: ExportJob) -> None
  + find_by_id(job_id: UUID) -> ExportJob?
  + find_by_user(
      user_id: UUID,
      page: int = 1,
      page_size: int = 10
    ) -> PaginatedResult[ExportJob]
  + find_active_by_user(user_id: UUID) -> list[ExportJob]
      Returns PENDING or PROCESSING jobs (for rate limiting)
  + find_expired() -> list[ExportJob]
      For cleanup job
```

## 11. Acceptance Criteria

### Export Formats

- [ ] CSV export produces valid UTF-8 with BOM, comma-delimited file
- [ ] CSV includes header row with column names
- [ ] CSV dates use ISO 8601, amounts are plain decimals
- [ ] JSON export produces valid JSON with hierarchical structure (accounts → transactions)
- [ ] JSON amounts are string decimals (not floats)
- [ ] JSON includes export metadata (exported_at, format_version, scope)
- [ ] PDF produces formatted statement with account summary, transaction table, and totals
- [ ] OFX produces valid OFX 2.2 XML for single-account exports

### Export Scopes

- [ ] FULL_DATA exports all user's personal data (GDPR compliant)
- [ ] FULL_DATA only available in JSON format
- [ ] ACCOUNT scope exports specific accounts' data
- [ ] DATE_RANGE scope filters transactions by date
- [ ] OFX only supports single-account scope
- [ ] include_deleted option includes soft-deleted items
- [ ] Authorization enforced — cannot export data from unauthorized accounts

### Job Lifecycle

- [ ] Export request creates job in PENDING status
- [ ] Processing sets status to PROCESSING
- [ ] Successful generation sets status to READY with download URL
- [ ] Download URL valid for 24 hours
- [ ] After URL expiry, status transitions to EXPIRED and file is cleaned up
- [ ] Failed generation sets status to FAILED with error message
- [ ] Maximum 3 concurrent active jobs per user

### GDPR Compliance

- [ ] Full export includes: profile, accounts, transactions, cards, categories, shares, preferences
- [ ] Full export excludes: passwords, bank credentials, audit logs, other users' data
- [ ] Export available within target time (< 1 hour for typical dataset)
- [ ] Export is free of charge

### Notifications

- [ ] `ExportCompleted` event triggers notification to user
- [ ] `ExportFailed` event triggers notification to user

### Security

- [ ] Download URLs are signed (non-guessable)
- [ ] Download only via HTTPS
- [ ] Users can only access their own export jobs
- [ ] Expired files are permanently deleted

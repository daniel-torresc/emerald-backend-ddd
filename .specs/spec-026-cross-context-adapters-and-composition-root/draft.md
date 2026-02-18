# Spec 026: Cross-Context Adapters & Composition Root

**Status:** Draft
**Bounded Context:** Infrastructure (Cross-Cutting)
**Dependencies:** 021 (Configuration & Database Foundation), 022 (IAM Persistence), 023 (Auth Infrastructure Adapters), 024 (Core Finance Persistence), 025 (Classification & Integrations Persistence)
**Blocks:** 027

---

## 1. Overview

This spec wires everything together — ACL adapters that bridge bounded contexts, a bank provider adapter registry, a manual DI composition root, and the FastAPI application factory.

**Key Principle:** No DI framework. The composition root is a plain Python factory function that constructs the full object graph manually. FastAPI `Depends()` is used for request-scoped injection. Cross-context adapters implement ports from one context using infrastructure from another.

## 2. Scope

### In Scope

- `TransactionAccessAdapter` (Classification → Core Finance)
- `TransactionImportAdapter` (Integrations → Core Finance)
- `DefaultBankProviderAdapterRegistry` with dev stub
- `DefaultTransactionNormalizer`
- Composition root (`Container` dataclass + factory function)
- FastAPI application factory with lifespan management
- Event handler wiring (domain events → handler methods)

### Out of Scope

- API middleware and error handlers (spec 027)
- Specific API routes (specs 028-030)
- Docker containerization (spec 031)

## 3. Cross-Context Adapters

### 3.1 TransactionAccessAdapter

Bridges the Classification context to Core Finance data:

```
TransactionAccessAdapter:
    """Implements classification.ports.TransactionAccessPort
    using Core Finance repositories."""

    __init__(session_factory: async_sessionmaker)

    async transaction_exists(transaction_id: UUID) -> bool
        Creates session, queries cf_transactions table
        Returns True if transaction exists and not deleted

    async get_transaction_account_id(transaction_id: UUID) -> UUID | None
        Returns account_id for a transaction (for ownership verification)
```

**Port implemented:** `TransactionAccessPort` (spec 014)

### 3.2 TransactionImportAdapter

Bridges the Integrations context to Core Finance for transaction creation:

```
TransactionImportAdapter:
    """Implements integrations.ports.TransactionImportPort
    using Core Finance services/repos."""

    __init__(core_finance_uow_factory: Callable)

    async import_transactions(
        account_id: UUID,
        transactions: list[NormalizedTransaction],
        import_source: ImportSource
    ) -> list[UUID]
        Creates Transaction domain objects from normalized data
        Persists via Core Finance UoW
        Returns list of created transaction IDs
```

**Port implemented:** `TransactionImportPort` (spec 015)

### 3.3 DefaultBankProviderAdapterRegistry

Maps provider names to concrete adapter implementations:

```
DefaultBankProviderAdapterRegistry:
    """Implements integrations.ports.BankProviderAdapterRegistry"""

    __init__():
        Registers built-in adapters (initially just a dev stub)

    get_adapter(provider: BankProvider) -> BankProviderAdapter
        Returns adapter for given provider
        Raises: ProviderNotSupportedError if no adapter registered

    get_normalizer(provider: BankProvider) -> TransactionNormalizer
        Returns normalizer for given provider
```

**Port implemented:** `BankProviderAdapterRegistry` (spec 015)

### 3.4 DefaultTransactionNormalizer

Basic normalizer for development and testing:

```
DefaultTransactionNormalizer:
    """Implements integrations.ports.TransactionNormalizer"""

    normalize(raw: RawBankTransaction) -> NormalizedTransaction
        Maps raw dict fields to NormalizedTransaction
        Handles date parsing, amount normalization
```

**Port implemented:** `TransactionNormalizer` (spec 015)

### 3.5 DevStubBankProviderAdapter

Stub adapter for development/testing without real bank APIs:

```
DevStubBankProviderAdapter:
    """Implements BankProviderAdapter for development."""

    async fetch_transactions(...) -> list[RawBankTransaction]
        Returns empty list or configurable test data

    async verify_credentials(...) -> bool
        Always returns True

    async get_account_info(...) -> ExternalAccountInfo
        Returns stub account info
```

## 4. Composition Root

### 4.1 Container Dataclass

```
@dataclass(frozen=True)
class Container:
    """Holds all application services, repositories, and infrastructure."""

    # Settings
    settings: AppSettings

    # Database
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    # Auth infrastructure
    password_hasher: Argon2PasswordHasher
    token_service: JwtTokenService
    oidc_provider: OidcProviderAdapter

    # IAM services
    registration_service: RegistrationService
    authentication_service: AuthenticationService
    role_management_service: RoleManagementService
    superadmin_provisioning_service: SuperadminProvisioningService

    # Core Finance services
    account_management_service: AccountManagementService
    account_sharing_service: AccountSharingService
    transaction_management_service: TransactionManagementService
    bulk_transaction_service: BulkTransactionService

    # Classification services
    taxonomy_management_service: TaxonomyManagementService
    transaction_categorization_service: TransactionCategorizationService

    # Integrations services
    bank_connection_service: BankConnectionService
    bank_sync_service: BankSyncService

    # Lifecycle services
    retention_policy_service: RetentionPolicyService

    # UoW factories (for request-scoped UoW creation)
    iam_uow_factory: Callable[[], AbstractIamUnitOfWork]
    core_finance_uow_factory: Callable[[], AbstractCoreFinanceUnitOfWork]
    classification_uow_factory: Callable[[], AbstractClassificationUnitOfWork]
    integrations_uow_factory: Callable[[], AbstractIntegrationsUnitOfWork]
```

### 4.2 Container Factory

```
def create_container(settings: AppSettings) -> Container:
    """Manual DI — constructs the full object graph."""

    # 1. Database
    engine = create_async_engine_from_settings(settings.database)
    session_factory = create_session_factory(engine)

    # 2. Auth adapters
    password_hasher = Argon2PasswordHasher()
    token_service = JwtTokenService(settings.jwt)
    http_client = httpx.AsyncClient()
    oidc_provider = OidcProviderAdapter(settings.oidc, http_client)

    # 3. UoW factories
    iam_uow_factory = lambda: SqlAlchemyIamUnitOfWork(session_factory)
    core_finance_uow_factory = lambda: SqlAlchemyCoreFinanceUnitOfWork(session_factory)
    classification_uow_factory = lambda: SqlAlchemyClassificationUnitOfWork(session_factory)
    integrations_uow_factory = lambda: SqlAlchemyIntegrationsUnitOfWork(session_factory)

    # 4. Cross-context adapters
    transaction_access_adapter = TransactionAccessAdapter(session_factory)
    transaction_import_adapter = TransactionImportAdapter(core_finance_uow_factory)
    provider_registry = DefaultBankProviderAdapterRegistry()

    # 5. Domain services (wired with ports)
    registration_service = RegistrationService(...)
    authentication_service = AuthenticationService(...)
    # ... (all services constructed with their dependencies)

    return Container(...)
```

### 4.3 No DI Framework

Rationale for manual composition:
- Full type safety — no runtime magic
- Explicit dependency graph — easy to trace
- No framework lock-in
- Simple to understand and debug
- Construction errors caught at startup, not at request time

## 5. FastAPI Application Factory

### 5.1 App Factory

```
def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Creates and configures the FastAPI application."""

    if settings is None:
        settings = AppSettings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        container = create_container(settings)
        app.state.container = container
        yield
        # Shutdown
        await container.engine.dispose()

    app.router.lifespan_context = lifespan

    # Register routers (specs 028-030)
    # Register middleware (spec 027)
    # Register error handlers (spec 027)

    return app
```

### 5.2 Container Access

```
def get_container(request: Request) -> Container:
    """FastAPI dependency — retrieves container from app state."""
    return request.app.state.container
```

### 5.3 Lifespan Management

| Phase | Actions |
|-------|---------|
| Startup | Load settings, create container (engine, session factory, all services) |
| Running | Container available via `app.state.container` |
| Shutdown | Dispose engine (close connection pool), close httpx client |

## 6. Event Handler Wiring

### 6.1 Domain Event Dispatch

Domain events collected from aggregates are dispatched to handlers after UoW commit:

```
Event dispatch pattern (in application services):
    1. Perform domain operation (aggregate emits events)
    2. Commit UoW
    3. Collect events from aggregate
    4. Dispatch to registered handlers

Handler registration (in composition root):
    categorization_event_handler = TransactionCategorizationService(...)
    # Wire: TermDeleted → categorization_event_handler.handle_term_deleted
    # Wire: TaxonomyDeleted → categorization_event_handler.handle_taxonomy_deleted
    # Wire: TransactionDeleted → categorization_event_handler.handle_transaction_deleted
```

**Note:** Event dispatch is synchronous within the same request (not async message bus). This is sufficient for the current architecture where events are used for cascade cleanup.

## 7. File Structure

```
src/emerald/infrastructure/
    adapters/
        __init__.py
        transaction_access_adapter.py
        transaction_import_adapter.py
        bank_provider_registry.py
        default_normalizer.py
        dev_stub_provider.py
    container.py      # Container dataclass + create_container()
    app.py            # FastAPI app factory + lifespan
```

## 8. Acceptance Criteria

### Cross-Context Adapters

- [ ] `TransactionAccessAdapter` queries Core Finance tables to check transaction existence
- [ ] `TransactionAccessAdapter` returns account_id for ownership checks
- [ ] `TransactionImportAdapter` creates real Transaction entities in Core Finance
- [ ] `DefaultBankProviderAdapterRegistry` returns adapter by provider name
- [ ] `DefaultBankProviderAdapterRegistry` raises on unsupported provider
- [ ] `DefaultTransactionNormalizer` converts raw data to NormalizedTransaction
- [ ] `DevStubBankProviderAdapter` works for development without real bank APIs

### Composition Root

- [ ] `create_container()` constructs all services with correct dependencies
- [ ] Container is a frozen dataclass (immutable after creation)
- [ ] All protocol ports are satisfied by concrete implementations
- [ ] UoW factories create new instances per call (request-scoped)
- [ ] Construction errors (missing settings) fail at startup
- [ ] No DI framework used — pure manual wiring

### FastAPI App Factory

- [ ] `create_app()` returns configured FastAPI instance
- [ ] Lifespan creates container on startup
- [ ] Lifespan disposes engine on shutdown
- [ ] Container accessible via `request.app.state.container`
- [ ] Swagger docs available only in debug mode
- [ ] App factory accepts optional settings override (for testing)

### Event Wiring

- [ ] Categorization event handlers connected at composition root
- [ ] Events dispatched synchronously after UoW commit
- [ ] Handler failures don't corrupt the committed transaction

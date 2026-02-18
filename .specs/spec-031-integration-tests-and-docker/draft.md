# Spec 031: Integration Tests & Docker

**Status:** Draft
**Bounded Context:** Infrastructure (Cross-Cutting)
**Dependencies:** 028 (REST API — IAM), 029 (REST API — Core Finance), 030 (REST API — Classification & Integrations)
**Blocks:** None

---

## 1. Overview

This spec defines full-stack end-to-end integration tests that exercise the complete request lifecycle (HTTP → middleware → service → repository → database), plus Docker containerization for deployment.

**Key Principle:** E2E tests use a real PostgreSQL database (via testcontainers) and the real FastAPI application. They verify that all layers work together correctly — from HTTP request to database persistence and back. Docker packaging enables consistent deployment across environments.

## 2. Scope

### In Scope

- E2E test flows covering major user journeys
- Test infrastructure: real PostgreSQL via testcontainers, Alembic migrations applied
- Shared test fixtures: app client, database, auth helpers
- Dockerfile (multi-stage build)
- docker-compose.yml (app + PostgreSQL)
- Database initialization via Alembic on startup

### Out of Scope

- Load/performance testing
- CI/CD pipeline configuration (GitHub Actions, etc.)
- Production deployment (Kubernetes, cloud services)
- Monitoring and observability setup

## 3. Test Infrastructure

### 3.1 PostgreSQL Testcontainer

```
@pytest.fixture(scope="session")
async def postgres_container():
    """Starts a real PostgreSQL container for the test session."""
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    yield container
    container.stop()
```

### 3.2 Database Setup

```
@pytest.fixture(scope="session")
async def database_url(postgres_container):
    """Returns async database URL for the test container."""
    return postgres_container.get_connection_url().replace(
        "postgresql://", "postgresql+asyncpg://"
    )

@pytest.fixture(scope="session", autouse=True)
async def apply_migrations(database_url):
    """Applies all Alembic migrations to test database."""
    # Run alembic upgrade head against the test database
```

### 3.3 App Client

```
@pytest.fixture
async def app(database_url):
    """Creates FastAPI app with test settings."""
    settings = AppSettings(
        database=DatabaseSettings(url=database_url),
        jwt=JwtSettings(secret_key="test-secret"),
        ...
    )
    return create_app(settings)

@pytest.fixture
async def client(app):
    """AsyncClient for making HTTP requests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### 3.4 Auth Helpers

```
async def register_user(client, email, password, username, full_name) -> dict:
    """Helper: registers a user and returns the response."""

async def login_user(client, email, password) -> dict:
    """Helper: logs in and returns tokens."""

async def auth_headers(client, email, password) -> dict:
    """Helper: returns {'Authorization': 'Bearer <token>'} for authenticated requests."""
```

## 4. E2E Test Flows

### 4.1 Auth Flow

```
test_auth_full_lifecycle:
    1. Register user → 201
    2. Login with credentials → 200 (tokens returned)
    3. Access /users/me with access token → 200
    4. Refresh token → 200 (new tokens)
    5. Access /users/me with new token → 200
    6. Logout → 204
    7. Old refresh token rejected → 401
```

### 4.2 Account Lifecycle

```
test_account_lifecycle:
    1. Register + login as user A
    2. Create account → 201 (with OWNER share)
    3. List accounts → includes new account
    4. Get account → full details with balance
    5. Update account name → 200
    6. Register + login as user B
    7. Share account with user B (EDITOR) → 201
    8. User B lists accounts → includes shared account
    9. User B creates transaction → 201 (EDITOR can write)
    10. Get balance → reflects new transaction
    11. Soft delete account → 204
    12. List accounts → account not in list
    13. List accounts (include_deleted=true) → account present
    14. Recover account → 200
    15. List accounts → account back in list
```

### 4.3 Transaction Splitting

```
test_transaction_split_flow:
    1. Setup: create account + single transaction (-100.00)
    2. Split transaction into 3 children (-40, -35, -25)
    3. Verify parent is_split_parent=true
    4. Verify 3 children exist
    5. Verify balance excludes parent, includes children
    6. Join splits → parent restored, children removed
    7. Verify balance reflects original amount
```

### 4.4 Bulk Operations

```
test_bulk_operations_flow:
    1. Setup: create account
    2. Bulk create 5 transactions → all succeed
    3. Verify balance reflects all 5
    4. Bulk update 3 transactions (change merchant) → all succeed
    5. Bulk delete 2 transactions → succeed
    6. Verify balance reflects remaining 3
    7. Bulk recover 2 → succeed
    8. Verify balance reflects all 5 again
```

### 4.5 Bank Sync Flow

```
test_bank_sync_flow:
    1. Setup: create account, register user
    2. Initiate bank connection → 201 (PENDING)
    3. Activate connection → 200 (ACTIVE)
    4. Trigger sync → 202
    5. Check sync history → shows IN_PROGRESS then SUCCESS
    6. List pending transactions (NEEDS_REVIEW)
    7. Approve one pending → creates real transaction
    8. Reject one pending → no transaction created
    9. Verify account balance includes approved transaction
    10. Disconnect connection → DISCONNECTED
```

### 4.6 Classification & Categorization

```
test_classification_flow:
    1. Create taxonomy "Expenses"
    2. Add root term "Food"
    3. Add child term "Groceries" under "Food"
    4. Add child term "Restaurants" under "Food"
    5. Reorder: Restaurants before Groceries
    6. Create account + transaction
    7. Assign "Groceries" to transaction
    8. List transaction categories → shows assignment
    9. Reassign to "Restaurants" (same taxonomy) → replaces
    10. Delete "Food" term → cascades to children
    11. Verify categorization assignments cleaned up
```

### 4.7 Cross-Context Cascade

```
test_cross_context_cascade:
    1. Create account with transactions and categories
    2. Create taxonomy with terms assigned to transactions
    3. Soft delete taxonomy → terms cascade deleted
    4. Verify categorization assignments removed
    5. Recover taxonomy → terms stay deleted (by design)
    6. Delete account → transactions cascade deleted
    7. Verify categorization assignments cleaned up (transaction deletion)
```

### 4.8 Permission Matrix

```
test_permission_enforcement:
    1. Create account as user A (OWNER)
    2. Share with user B (EDITOR), user C (VIEWER)
    3. User C: GET transactions → 200 (VIEWER can read)
    4. User C: POST transaction → 403 (VIEWER can't write)
    5. User B: POST transaction → 201 (EDITOR can write)
    6. User B: DELETE account → 403 (EDITOR can't delete)
    7. User A: DELETE account → 204 (OWNER can delete)
```

## 5. Dockerfile

### 5.1 Multi-Stage Build

```dockerfile
# Stage 1: Builder
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy source
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Stage 2: Runtime
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy installed packages and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn emerald.infrastructure.app:create_app --host 0.0.0.0 --port 8000 --factory"]
```

### 5.2 Key Decisions

| Decision | Rationale |
|----------|-----------|
| Multi-stage build | Smaller runtime image (no build tools) |
| `python:3.13-slim` | Minimal base, Python 3.13+ required |
| `uv` for deps | Consistent with development workflow |
| Migrations in CMD | Ensures DB is up to date on every deploy |
| `--factory` flag | uvicorn calls `create_app()` at startup |

## 6. Docker Compose

### 6.1 docker-compose.yml

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://emerald:emerald@db:5432/emerald
      - JWT_SECRET_KEY=change-me-in-production
      - ENVIRONMENT=development
      - DEBUG=true
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=emerald
      - POSTGRES_PASSWORD=emerald
      - POSTGRES_DB=emerald
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U emerald"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
```

### 6.2 Service Dependencies

| Service | Depends On | Health Check |
|---------|-----------|-------------|
| `app` | `db` (healthy) | HTTP GET /health |
| `db` | — | pg_isready |

## 7. New Dev Dependencies

| Package | Purpose |
|---------|---------|
| `testcontainers[postgres]` | Real PostgreSQL for integration tests |
| `httpx` | AsyncClient for testing FastAPI |
| `pytest-asyncio` | Async test support (if not already present) |

## 8. File Structure

```
tests/
    e2e/
        __init__.py
        conftest.py                    # Shared fixtures (container, app, client, helpers)
        test_auth_flow.py
        test_account_lifecycle.py
        test_transaction_splitting.py
        test_bulk_operations.py
        test_bank_sync_flow.py
        test_classification_flow.py
        test_cross_context_cascade.py
        test_permission_matrix.py
Dockerfile
docker-compose.yml
```

## 9. Acceptance Criteria

### E2E Tests

- [ ] All test flows pass against real PostgreSQL
- [ ] Migrations applied automatically before tests
- [ ] Each test is isolated (clean database state or unique data)
- [ ] Tests run with `uv run pytest tests/e2e/` command
- [ ] Auth helper creates and authenticates users for testing
- [ ] Tests cover happy paths and key error scenarios

### Test Infrastructure

- [ ] PostgreSQL container starts and stops cleanly
- [ ] Alembic migrations run against test database
- [ ] FastAPI test client works with async endpoints
- [ ] Test database is isolated from development database

### Auth Flow

- [ ] Register → login → access → refresh → logout lifecycle works
- [ ] Token rotation invalidates old refresh token
- [ ] Expired tokens properly rejected

### Account Lifecycle

- [ ] Create → share → transact → delete → recover flow works
- [ ] Balance correctly calculated through lifecycle
- [ ] Shares visible to shared users

### Transaction Flows

- [ ] Split → verify children → verify balance → join works
- [ ] Bulk create/update/delete/recover with per-item results
- [ ] Balance excludes deleted and split parents

### Cross-Context

- [ ] Taxonomy deletion cascades to categorization assignments
- [ ] Transaction deletion cleans up categorization
- [ ] Bank sync creates real transactions in Core Finance

### Permission Enforcement

- [ ] VIEWER: read-only access
- [ ] EDITOR: read + write, no delete
- [ ] OWNER: full access including delete and share management
- [ ] No share: 403 on all account operations

### Docker

- [ ] `docker compose up` starts app + database
- [ ] App waits for database to be healthy
- [ ] Migrations run on startup
- [ ] Health endpoint responds after startup
- [ ] App accessible on port 8000
- [ ] `docker compose down` cleans up

### Build

- [ ] Docker image builds successfully
- [ ] Image size is reasonable (< 500MB)
- [ ] No dev dependencies in production image
- [ ] Python 3.13+ used in runtime

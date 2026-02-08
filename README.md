# emerald-backend-ddd

Emerald Finance Platform — a personal and family finance management system built with Domain-Driven Design in Python.

## Features

- **Shared Kernel** (Spec-001) — Foundation value objects (`Money`, `Currency`, `DateRange`, `RetentionPeriod`), entity traits (`Entity`, `AggregateRoot`, mixins for timestamps/audit/soft-delete), `DomainEvent` base, and a domain exception hierarchy.
- **User Registration & Identity** (Spec-002) — `User` aggregate root with full lifecycle state machine (Pending → Active → Suspended → Deleted), email/username value objects, password strength validation, auth provider management (password + Google/Microsoft), and a `UserRegistrationService` application service.
- **Authentication & Sessions** (Spec-003) — Password-based login, JWT access tokens (15-min TTL), refresh token rotation with family-based theft detection, concurrent session limits (max 5), `AuthenticatedIdentity` cross-context contract, password reset flow (single-use, 1-hour tokens), and portal-aware token TTLs (regular vs admin).

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package and project manager)

## Setup

```bash
# Install all dependencies
uv sync

# Rebuild after source changes
uv sync --reinstall-package emerald-backend
```

## Architecture

The project follows **Ports & Adapters** (Hexagonal Architecture) with DDD bounded contexts:

```
src/emerald/
├── shared_kernel/          # Cross-context foundation types
│   ├── domain/             # Value objects, entities, events, exceptions
│   └── application/        # Base Command, AbstractUnitOfWork
└── iam/                    # Identity & Access Management context
    ├── domain/
    │   ├── models/         # User aggregate, value objects, token entities
    │   ├── events/         # Domain events (user + auth lifecycle)
    │   ├── exceptions/     # IAM-specific exceptions
    │   ├── ports/          # PasswordHasher, TokenService protocols
    │   ├── services/       # Password validation functions
    │   └── constants.py    # Domain constants (TTLs, session limits)
    └── application/
        ├── dto/            # Commands and DTOs (LoginResult, etc.)
        ├── ports/outbound/ # UserRepository, token repos, UnitOfWork
        └── services/       # UserRegistrationService, AuthenticationService
```

Specifications live in `.specs/` — see [`.specs/README.md`](.specs/README.md) for the full catalog and dependency graph.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests for a specific bounded context
uv run pytest tests/unit/iam/
uv run pytest tests/unit/shared_kernel/

# Run a specific test module
uv run pytest tests/unit/iam/domain/models/test_user.py
```

## Code Quality

```bash
# Lint (check for errors)
uv run ruff check .

# Lint and auto-fix
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check formatting without changes
uv run ruff format --check .

# Type checking
uv run ty check
```

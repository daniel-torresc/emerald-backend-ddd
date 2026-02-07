# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Emerald Finance Platform - Backend**: A comprehensive personal and family finance management system built with Domain-Driven Design. The platform serves as the single source of truth for all financial accounts, transactions, and budgets across institutions.

**What it does:** Users track accounts in any currency, record and categorize transactions, share accounts with family (Owner/Editor/Viewer permissions), connect to banks for automatic imports, and manage their complete financial picture. The system is organized into four bounded contexts: IAM (identity & auth), Core Finance (accounts, transactions, cards, sharing), Classification (taxonomies & categorization), and External Integrations (bank connections & sync).

**Specifications:** Incremental business specs live in `.specs/` — see `.specs/README.md` for the full catalog and dependency graph.

**Tech Stack:**

- Python 3.13+
- Python package and project management: `uv` (MANDATORY - never use pip/poetry)
- Code linting: ``ruff`` 
  - Format code ``uv run ruff format .``
  - Lint and auto-fix: ``uv run ruff check --fix .``
- Type checking: ``ty`` 
  - ``uv run ty check``

## Key Instructions

- When building features, **consult the `architecture-patterns` skill** for established best practices and design patterns
- ALWAYS follow the `ports-and-adapters` project structure from the `architecture-patterns` skill. Use it for each bounded context
- Apply these architectural guidelines to ensure consistency and maintainability across the codebase
- If uncertain about how to structure a feature, review the relevant patterns in the skill before proceeding

## Project Conventions

- **Bounded contexts** live under `src/emerald/{context}/`
- **Value objects**: `@dataclass(frozen=True)` with validation in `__post_init__`
- **Entity traits**: cooperative mixins using `super().__init__(**kwargs)` with `**kwargs: Any` for MRO forwarding
- **Ports**: `typing.Protocol` (structural subtyping) — no ABC inheritance
- **Domain events**: `@dataclass(frozen=True)` extending `DomainEvent`, with `aggregate_type` class var
- **Commands**: `@dataclass(frozen=True)` extending `Command` base from shared kernel
- **Exceptions**: extend the shared kernel hierarchy (`DomainError` → `InvalidValueError`, `InvariantViolationError`, etc.), each with a unique `code`
- **Test fakes**: put in `tests/unit/{context}/fakes.py` — in-memory repository/UoW/hasher implementations
- **Public API**: each context's `__init__.py` re-exports all public types with explicit `__all__`

## Common Commands

```bash
# Install dependencies
uv sync

# Rebuild after source changes
uv sync --reinstall-package emerald-backend

# Run all tests
uv run pytest

# Run tests verbose
uv run pytest -v

# Run specific test file
uv run pytest tests/unit/shared_kernel/value_objects/test_money.py

# Lint + auto-fix
uv run ruff check --fix .

# Format
uv run ruff format .

# Type check
uv run ty check
```

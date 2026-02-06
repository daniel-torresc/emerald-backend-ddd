# emerald-backend-ddd

Emerald Finance Platform — a personal and family finance management system built with Domain-Driven Design in Python.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package and project manager)

## Setup

```bash
# Install all dependencies
uv sync
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run a specific test module
uv run pytest tests/unit/shared_kernel/value_objects/test_money.py

# Run a specific test class or function
uv run pytest tests/unit/shared_kernel/entities/test_entity.py::TestEntityEquality
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

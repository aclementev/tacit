[private]
default:
    @just --list

# Run linting and format check (ruff check + ruff format --check + pyright)
lint:
    uv run ruff check
    uv run ruff format --check
    uv run pyright

# Run the formatter and auto-fixable lint issues
fix:
    uv run ruff check --fix
    uv run ruff format

# Run the test suite
test *args:
    uv run pytest tests {{args}}

# Run all checks (lint + tests)
check:
    just lint
    just test

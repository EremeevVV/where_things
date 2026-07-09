# AGENTS.md

## What this is

Yandex Alice voice skill: user says "запомни, что паспорт лежит в ящике", skill remembers. Later: "где лежит паспорт?" — skill answers.

Stack: Python 3.14, Yandex Cloud Functions (webhook), YDB serverless.

## Key files

- `PROJECT_INSTRUCTIONS.md` — full project context, constraints, architecture decisions, iteration log. **Read this first.**
- `KICKOFF_PROMPT.md` — iteration plan and current task.
- `main.py` — handler (`handler(event, context)`) for Yandex Cloud Functions.
- `nlu.py` — NLU parser: `Intent` enum, `parse_intent()`.
- `states.py` — State pattern: `DialogState` ABC, `StateName` enum, `IdleState`, `AwaitingPlaceState`, `build_response()`.
- `repository.py` — `ItemsRepository` Protocol (interface).
- `ydb_repository.py` — `YdbItemsRepository` (YDB implementation).
- `memory_repository.py` — `InMemoryItemsRepository` (fake for tests).

## Commands

```bash
# Run handler directly (loads launch.json, prints response)
uv run python main.py

# Install deps
uv sync

# Add a dependency
uv add <package>
```

## Local testing

```bash
# pytest — full test suite
uv run python -m pytest

# Single test
uv run python -m pytest tests/test_handler.py::TestLaunch::test_greeting_contains_hint -v

# Manual test runner (all scenarios)
uv run python tests/test_handler_manual.py

# Manual test runner (single scenario)
uv run python tests/test_handler_manual.py launch

# Cloud Functions simulator — checks timing, warns on violations
uv run python tests/test_runner.py

# Linting
uv run python -m ruff check .

# Auto-fix linting issues
uv run python -m ruff check . --fix

# Type checking
uv run python -m mypy main.py --ignore-missing-imports --strict
```

Sample events live in `test_data/`. Edit or add JSON files there to test new scenarios. Fixtures in `tests/conftest.py` load them by name.

## Tests and test infrastructure

All test files and test utilities MUST live in the `tests/` folder. Never place test files in the project root.

```
tests/
├── conftest.py                  # pytest fixtures
├── test_handler.py              # unit tests for handler and parse_intent
├── test_handler_manual.py       # manual test runner (invoked via CLI)
├── test_runner.py               # Cloud Functions simulator with timing checks
├── test_states_with_repo.py     # integration tests with InMemoryItemsRepository
└── test_ydb.py                  # YDB integration tests (skipped without env vars)
```

If you create a new test file, place it in `tests/`. If you create a new test utility (runner, simulator, fixture loader), place it in `tests/` as well.

## Platform constraints (non-obvious)

- Response must complete within **4.5 seconds** or session drops.
- `session_state` ≤ 1 KB — lost between turns if not returned in response.
- Response text ≤ 5000 characters.
- Activation name must NOT contain "Яндекс", "Алиса", "Станция", "открой", "запусти".
- Long-term memory only works for users authorized via Yandex ID (always authorized on Station).

## Development approach

Work in iterations per `KICKOFF_PROMPT.md`. After each iteration, update the iteration log in `PROJECT_INSTRUCTIONS.md` section 9. One handler file, explicit functions per intent (`handle_save`, `handle_find`, `handle_list`, `handle_delete`), NLU parser separate.

## Post-build verification

After every code change, run the full verification pipeline and fix all issues before finishing:

```bash
uv run python -m ruff check . --fix && uv run python -m mypy main.py --ignore-missing-imports --strict && uv run python -m pytest -v
```

1. **ruff** — linting + auto-fix
2. **mypy** — static type checking
3. **pytest** — test suite

All three must pass with zero errors. If any step fails, fix the issues and re-run.

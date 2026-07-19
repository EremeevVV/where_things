# AGENTS.md

## What this is

Yandex Alice voice skill: user says "запомни, что паспорт лежит в ящике", skill remembers. Later: "где лежит паспорт?" — skill answers.

Stack: Python 3.14, aliceio, Yandex Cloud Functions (webhook), YDB serverless.

## Key files

- `PROJECT_INSTRUCTIONS.md` — full project context, constraints, architecture decisions, iteration log. **Read this first.**
- `KICKOFF_PROMPT.md` — iteration plan and current task.
- `main.py` — entry point: Dispatcher + YCF handler (~26 lines).
- `src/handlers.py` — all intent handlers: `handle_launch`, `handle_save`, `handle_find`, `handle_list_intent`, `handle_delete`, `handle_unknown`. FSM via `SaveForm`. `AuthMiddleware`.
- `src/repository.py` — `ItemsRepository` Protocol (interface).
- `src/ydb_repository.py` — `YdbItemsRepository` (YDB implementation).
- `src/memory_repository.py` — `InMemoryItemsRepository` (fake for tests).

## NLU

Intent parsing is done by Yandex Dialogs platform (not in code). Intents defined in the skill console:
- `save` — slots: `thing`, `place`
- `find` — slot: `thing`
- `list` — no slots
- `delete` — slot: `thing`

The code receives pre-parsed intents via `message.nlu.intents`.

## Commands

```bash
# Run tests (use --no-sync due to aiohttp version conflict in lockfile)
uv run --no-sync python -m pytest

# Or run directly with venv python
.venv\Scripts\python.exe -m pytest

# Install deps
uv sync

# Add a dependency
uv add <package>
```

**Note:** `uv run` without `--no-sync` may fail because the lockfile pins aiohttp 3.11.x but the environment has 3.14.1 (from ydb). Always use `uv run --no-sync` or `.venv\Scripts\python.exe` directly.

## Local testing

```bash
# pytest — full test suite
uv run --no-sync python -m pytest

# Single test
uv run --no-sync python -m pytest tests/test_handler.py::TestLaunch::test_greeting_contains_hint -v

# Manual test runner (all scenarios)
uv run --no-sync python tests/test_handler_manual.py

# Manual test runner (single scenario)
uv run --no-sync python tests/test_handler_manual.py launch

# Cloud Functions simulator — checks timing, warns on violations
uv run --no-sync python tests/test_runner.py

# Linting
.venv\Scripts\python.exe -m ruff check .

# Auto-fix linting issues
.venv\Scripts\python.exe -m ruff check . --fix

# Code formatting
.venv\Scripts\python.exe -m ruff format .

# WPS style checks
.venv\Scripts\python.exe -m flake8 --select=WPS .

# Type checking
.venv\Scripts\python.exe -m mypy main.py --ignore-missing-imports --strict
```

## Tests and test infrastructure

All test files and test utilities MUST live in the `tests/` folder. Never place test files in the project root.

```
tests/
├── test_handler.py              # unit tests for handlers (async, uses asyncio.run)
├── test_handler_manual.py       # manual test runner (invoked via CLI)
├── test_runner.py               # Cloud Functions simulator with timing checks
├── test_states_with_repo.py     # integration tests with InMemoryItemsRepository
└── test_ydb.py                  # YDB integration tests (skipped without env vars)
```

Tests use `asyncio.run()` to call async handlers directly. Handlers receive `Message` objects (aliceio types) with `nlu.intents` populated.

## Platform constraints (non-obvious)

- Response must complete within **4.5 seconds** or session drops.
- `session_state` ≤ 1 KB — lost between turns if not returned in response.
- Response text ≤ 5000 characters.
- Activation name must NOT contain "Яндекс", "Алиса", "Станция", "открой", "запусти".
- Long-term memory only works for users authorized via Yandex ID (always authorized on Station).

## Development approach

Work in iterations per `KICKOFF_PROMPT.md`. After each iteration, update the iteration log in `PROJECT_INSTRUCTIONS.md` section 9. Use aliceio Dispatcher/Router pattern. Intents handled by Yandex Dialogs NLU.

## Post-build verification

After every code change, run the full verification pipeline and fix all issues before finishing:

```bash
.venv\Scripts\python.exe -m ruff format . && .venv\Scripts\python.exe -m ruff check . --fix && .venv\Scripts\python.exe -m flake8 --select=WPS . && .venv\Scripts\python.exe -m mypy main.py --ignore-missing-imports --strict && .venv\Scripts\python.exe -m pytest -v
```

1. **ruff format** — code formatting
2. **ruff check --fix** — linting + auto-fix
3. **flake8 --select=WPS** — WPS style checks
4. **mypy** — static type checking
5. **pytest** — test suite

All five must pass with zero errors. If any step fails, fix the issues and re-run.

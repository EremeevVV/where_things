# AGENTS.md

## What this is

Yandex Alice voice skill: user says "запомни, что паспорт лежит в ящике", skill remembers. Later: "где лежит паспорт?" — skill answers.

Stack: Python 3.14, Yandex Cloud Functions (webhook), YDB serverless.

## Key files

- `PROJECT_INSTRUCTIONS.md` — full project context, constraints, architecture decisions, iteration log. **Read this first.**
- `KICKOFF_PROMPT.md` — iteration plan and current task.
- `main.py` — handler (`handler(event, context)`) for Yandex Cloud Functions.
- `test_runner.py` — local simulator with timing and warnings.

## Commands

```bash
# Run handler directly (loads launch.json, prints response)
uv run python main.py

# Install deps (when dependencies are added)
uv sync

# Add a dependency
uv add <package>
```

No linting or formatting configured yet.

## Local testing

```bash
# Quick check — runs handler against sample events, prints responses
uv run python test_handler.py

# Single event only
uv run python test_handler.py launch

# Cloud Functions simulator — checks timing, warns on violations
uv run python test_runner.py

# pytest — full test suite
uv run python -m pytest

# Single test
uv run python -m pytest tests/test_handler.py::TestLaunch::test_greeting_contains_hint -v

# Linting
uv run python -m ruff check .

# Auto-fix linting issues
uv run python -m ruff check . --fix

# Type checking
uv run python -m mypy main.py --ignore-missing-imports --strict
```

Sample events live in `test_data/`. Edit or add JSON files there to test new scenarios. Fixtures in `tests/conftest.py` load them by name.

## Platform constraints (non-obvious)

- Response must complete within **4.5 seconds** or session drops.
- `session_state` ≤ 1 KB — lost between turns if not returned in response.
- Response text ≤ 5000 characters.
- Activation name must NOT contain "Яндекс", "Алиса", "Станция", "открой", "запусти".
- Long-term memory only works for users authorized via Yandex ID (always authorized on Station).

## Development approach

Work in iterations per `KICKOFF_PROMPT.md`. After each iteration, update the iteration log in `PROJECT_INSTRUCTIONS.md` section 9. One handler file, explicit functions per intent (`handle_save`, `handle_find`, `handle_list`, `handle_delete`), NLU parser separate.

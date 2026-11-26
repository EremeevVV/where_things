# AGENTS.md

## What this is

Yandex Alice voice skill: user says "запомни, что паспорт лежит в ящике", skill remembers. Later: "где лежит паспорт?" — skill answers.

Stack: Python 3.12, aliceio, Yandex Cloud Functions (webhook), YDB serverless.

## Key files

- `openspec/project.md` — полный контекст проекта: ограничения платформы, архитектура, ADR, история итераций. **Читать первым.**
- `openspec/specs/` — спеки текущих возможностей (истина о том, что реализовано).
- `openspec/changes/` — активные изменения (proposal/design/tasks/spec deltas).
- `main.py` — entry point: Dispatcher + YCF handler (~74 lines).
- `src/handlers.py` — все intent handlers + FSM (`SaveForm.awaiting_confirmation`) + `AuthMiddleware`.
- `src/nlu/` — типизированные интенты (`intents.py`, `slots.py`) и конвейер нормализации вещи (`thing/`: decomposer → canonicalizer → canonical_key).
- `src/db/` — `ItemsRepository` Protocol (`protocol.py`), YDB-реализация (`ydb.py`), InMemory фейк для тестов (`memory.py`).
- `alice_intents_grammars.md` — грамматики интентов для консоли Яндекс Диалогов.

## OpenSpec workflow

Новая работа начинается через slash-команды opencode:

- `/opsx-explore` — обдумать идею до кода
- `/opsx-propose <kebab-name>` — создать change (proposal + specs deltas + design + tasks)
- `/opsx-apply <change>` — реализовать по tasks.md
- `/opsx-sync <change>` — смержить дельты в основные спеки без архивации
- `/opsx-archive <change>` — финализировать: дельты → specs/, change → archive/

Спеки и артефакты пишутся на русском; сценарии — Gherkin внутри fenced-блоков
(конвенции в `openspec/config.yaml`). Изменение поведения кода = изменение спека.

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

# Debug logging (all NLU decomposition details)
LOG_LEVEL=DEBUG .venv\Scripts\python.exe -m pytest

# Warning-only logging (skip INFO)
LOG_LEVEL=WARNING .venv\Scripts\python.exe -m pytest
```

## Utility scripts

Use the helper scripts in `scripts/` for routine project tasks:

1. **Подготовка архива для выгрузки на площадку (Yandex Cloud Functions):**
   ```bash
   .venv\Scripts\python.exe scripts/build_ycf_zip.py
   ```
   Упаковывает `main.py`, `src/` и `requirements.txt` в `var/where_things.zip`.

2. **Подготовка файлов проекта для обновления во внешней LLM:**
   ```bash
   .venv\Scripts\python.exe scripts/collect_for_external.py
   ```
   Собирает исходники, спеки (`openspec/`), документацию и конфиги (без `.env`, кэшей и `var/`) в `var/flatten/`.

3. **Обновление дерева проекта в `AGENTS.md`:**
   ```bash
   .venv\Scripts\python.exe scripts/project_tree.py
   ```
   Генерирует актуальное дерево каталогов и файлов проекта для вставки в `AGENTS.md`.

## Tests and test infrastructure

All test files and test utilities MUST live in the `tests/` folder. Never place test files in the project root.

```
tests/
├── nlu/thing/                   # normalization pipeline tests (decomposer/canonicalizer/matcher/normalize)
├── conftest.py                  # shared fixtures
├── test_handler.py              # unit tests for handlers (async, uses asyncio.run)
├── test_handler_manual.py       # manual test runner (invoked via CLI)
├── test_nlu_logging.py          # intent logging tests
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

Работа идёт через OpenSpec changes (`/opsx-propose` → ревью → `/opsx-apply`). Спецификация поведения живёт в `openspec/specs/`; изменение наблюдаемого поведения кода требует обновления соответствующего спека. История изменений — в `openspec/changes/archive/`.

## Code style policy

**Не добавлять исключения в `setup.cfg`.** Устранять проблемы в коде, а не глушить линтер. Если WPS/ruff ругается — рефакторить код до зелёного состояния, а не добавлять `WPSxxx` в per-file-ignores.

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

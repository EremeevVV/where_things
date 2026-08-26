# where_things — навык Алисы «Где лежит вещь»

Постоянный контекст проекта. Читается перед созданием любых OpenSpec-артефактов.
Документ не меняется от change к change; история изменений живёт в
`openspec/changes/archive/` и в разделе «История итераций» ниже.

## 1. Назначение

Голосовой навык для Яндекс Алисы (в первую очередь — Яндекс Станция). Пользователь
голосом сообщает, куда положил вещь, навык запоминает пару (вещь, место), привязанную
к аккаунту. Позже пользователь спрашивает, где лежит вещь, — навык отвечает.

Базовые сценарии:

- Запись: «запомни, что <вещь> лежит <место>» → сохранить пару.
- Поиск: «где лежит <вещь>?» → вернуть место или сказать, что не знает.
- Список: «что ты помнишь?» → перечислить вещи.
- Удаление: «забудь про <вещь>».

## 2. Архитектура и стек (зафиксировано)

| Компонент | Выбор |
|---|---|
| Язык | **Python 3.12** (понижен с 3.14 из-за совместимости библиотек: ydb/aiohttp) |
| Фреймворк навыка | **aliceio** ≥ 0.2 (Dispatcher, Router, FSM, Middleware) |
| Хостинг | **Yandex Cloud Functions** — вебхук, бесплатны для навыков Алисы |
| БД | **YDB serverless**, таблица `items(user_id, canonical_key, display_name, location, verb)`, PK `(user_id, canonical_key)` |
| Морфология | **pymorphy3** (без тяжёлых NLP-моделей) |
| Пакеты | **uv**; тесты запускать через `uv run --no-sync` (конфликт aiohttp в lockfile) |
| NLU | Делегирован платформе Yandex Dialogs: код читает `message.nlu.intents` |

Ключ пользователя — `session.user.user_id` (стабилен для авторизованных через Яндекс ID;
на Станции пользователь всегда авторизован).

Почему YDB, а не встроенное хранилище Диалогов: `user_state` имеет лимит **1 КБ**,
чего может не хватить на список вещей. YDB снимает лимит и остаётся в той же
бесплатной экосистеме.

## 3. Жёсткие ограничения платформы (помнить всегда)

- Ответ навыка ≤ **4,5 секунды**, иначе сессия оборвётся. Соединение к YDB держать тёплым, запросы лёгкими.
- Долговременная память работает **только для авторизованных через Яндекс ID**. Неавторизованным — текст с просьбой авторизоваться (`AuthMiddleware`).
- `session_state` ≤ **1 КБ**. Если состояние не меняется, но нужно сохранить — вернуть тот же объект, что пришёл.
- Текст ответа ≤ **5000 символов**.
- Активационное имя НЕ должно содержать «Яндекс», «Алиса», «Станция», «открой», «запусти» и общеупотребительные слова. Нужны склонения и синонимы.
- После публикации Диалоги периодически пингуют навык; если он несколько часов молчит — отключат.

## 4. Уровни хранения (не путать)

- `session_state` — внутри одной сессии (машина состояний, уточняющие вопросы).
- `user_state` — между сессиями, только авторизованные, лимит 1 КБ, очистка `{}`.
- `application_state` — привязка к устройству, работает и для неавторизованных (запасной путь).

В проекте долговременные данные → YDB; FSM aliceio хранит шаги диалога внутри сессии.

## 5. NLU / интенты

Разбор фраз выполняет платформа Yandex Dialogs (интенты настраиваются в консоли,
грамматики — рабочий референс `alice_intents_grammars.md` в корне репозитория):

| Интент | Слоты | Назначение |
|---|---|---|
| `save` | `thing`, `place` | запись/обновление вещи |
| `find` | `thing` | поиск |
| `list` | — | список вещей |
| `delete` | `thing` | удаление |

Код получает предразобранные интенты через `message.nlu.intents`. Известная проблема:
два подряд свободных нетерминала `$Thing ... $Place` (оба `.+`) в грамматике save —
поведение парсера Диалогов на неоднозначности недокументировано, проверять на реальных
фразах из `test_data/`.

Нормализация сущности «вещь» выполняется локально: `normalize_thing()` (src/nlu/thing/)
строит `display_name` и `canonical_key`; идентичность вещи — точное совпадение ключа.

## 6. Эталон структуры ответа

```json
{
  "response": {
    "text": "Запомнила: паспорт — верхний ящик стола.",
    "tts": "Запомнила: паспорт — верхний ящик стола.",
    "end_session": false
  },
  "version": "1.0"
}
```

## 7. Чек-лист развёртывания

1. Yandex Cloud: облако + платёжный аккаунт (списаний за функции навыка нет).
2. Cloud Functions: функция, runtime Python, загрузить обработчик.
3. YDB serverless: база + таблица `items` (PK `(user_id, canonical_key)`).
4. Консоль Диалогов: создать диалог → Навык в Алисе; настроить интенты (см. §5).
5. Backend → «Функция в Яндекс Облаке» → выбрать функцию.
6. Включить «Использовать хранилище данных в навыке».
7. Активационное имя + склонения + синонимы.
8. Тип доступа → **Приватный** (тест голосом на своей Станции без публикации).
9. Тест на вкладке «Тестирование», затем голосом на колонке.

## 8. Процесс разработки

- Новая работа начинается с `/opsx-propose <kebab-name>` (обкатка идеи — `/opsx-explore`).
- Реализация — `/opsx-apply`, синхронизация дельт в основные спеки — `/opsx-sync`,
  финализация — `/opsx-archive` (история накапливается в `openspec/changes/archive/`).
- Code style policy: **не добавлять исключения в `setup.cfg`** — устранять проблемы в
  коде, а не глушить линтер. Расширение per-file-ignores — только с согласия владельца.
- Логи без PII: `user_id[:8]`, уровень через `LOG_LEVEL`.

### Верификация (после каждого изменения кода)

```bash
.venv\Scripts\python.exe -m ruff format . && .venv\Scripts\python.exe -m ruff check . --fix && .venv\Scripts\python.exe -m flake8 --select=WPS . && .venv\Scripts\python.exe -m mypy main.py --ignore-missing-imports --strict && .venv\Scripts\python.exe -m pytest -v
```

Все пять шагов должны проходить с нулём ошибок.

### Тестовая инфраструктура (всё в tests/)

| Файл | Роль |
|---|---|
| `test_handler.py` | юнит-тесты хендлеров (async, `asyncio.run`) |
| `test_states_with_repo.py` | интеграция с `InMemoryItemsRepository` |
| `test_nlu_logging.py` | логирование интентов |
| `nlu/thing/*` | конвейер нормализации (decomposer/canonicalizer/matcher/normalize) |
| `test_ydb.py` | интеграция с YDB (skipped без env-переменных) |
| `test_handler_manual.py` | ручной прогон сценариев из CLI |
| `test_runner.py` | симулятор Cloud Functions с проверкой тайминга |

Команды: `uv run --no-sync python -m pytest` или `.venv\Scripts\python.exe -m pytest`
(без `--no-sync` uv может упасть из-за конфликта aiohttp в lockfile).

## 9. Структура кода

```
main.py                 # entry point (~74 строки): JsonFormatter, Dispatcher+Skill, YCF handler
src/
  handlers.py           # все хендлеры интентов + AuthMiddleware + FSM SaveForm.awaiting_confirmation
  nlu/
    intents.py          # SaveIntent/FindIntent/DeleteIntent (+ display_name, canonical_key)
    slots.py            # get_intent(), get_slot() — извлечение данных из message.nlu
    thing/              # конвейер нормализации: decomposer → canonicalizer → matcher(canonical_key)
                        #   normalize.py = единая точка вызова normalize_thing()
  db/
    protocol.py         # ItemsRepository Protocol + dataclass ItemRecord
    memory.py           # InMemoryItemsRepository (тестовый фейк)
    ydb.py              # YdbItemsRepository (прод, YQL)
tests/                  # см. §8
test_data/              # JSON-фикстуры запросов для ручного прогона и симулятора
```

Поток зависимостей: `main.py → handlers.py → nlu/intents.py → slots.py → message.nlu.intents`,
нормализация: `→ thing/normalize.py → decompose → canonicalize → canonical_key`,
хранилище: `→ db/protocol.py → db/memory.py | db/ydb.py`.

### Ключевые решения (ADR)

| Решение | Описание |
|---|---|
| Intent parsing | Делегирован платформе Yandex Dialogs; код читает `message.nlu.intents` |
| Идентичность вещи | `canonical_key` = canonical_head#sorted(modifiers), точное совпадение |
| Нормализация | `normalize_thing()` — единственная точка вызова, вызывается из `intents.py` |
| Канонизация | Словарь-мэппер `canonical_dict.py` (MappingProxyType), тотальная функция |
| Морфология | pymorphy3, без тяжёлых NLP-моделей (Natasha, spaCy) |
| Поиск | Exact match через `find_by_canonical_key`, fuzzy-поиска нет |
| Коллизия canonical_key | Всегда FSM `awaiting_confirmation` (предложение обновить display_name) |
| DI репозитория | `Dispatcher(repo=...)` в main.py — единственная точка инъекции |
| Отказоустойчивость | Хендлеры возвращают осмысленный ответ, а не падают (fallback-ответ) |
| Логирование | stdlib logging + JSON formatter для Yandex Cloud Logging (stdout) |

## 10. История итераций

- Итерация 0 — подготовка инструкции и вводного промта. Статус: готово.
- Итерация 1 — минимальный обработчик + эхо/приветствие, проверка на вкладке Тестирование. Статус: готово.
- Итерация 2 — NLU-парсер (SAVE/FIND/LIST/DELETE/UNKNOWN), сохранение/поиск в `session_state`, тесты (24 passed). Статус: готово.
- Итерация 3 — машина состояний (State pattern). `IdleState`/`AwaitingPlaceState`, счётчик `state_visits` для эскалации подсказок, прерывание другой командой с возвратом в IDLE. 39 тестов. Статус: готово.
- Итерация 4 — Repository pattern: интерфейс `ItemsRepository` (Protocol), `YdbItemsRepository`, `InMemoryItemsRepository`; инъекция repo через параметр `handle()`. 53 теста. Статус: готово.
- Итерация 5 — чистый main.py + типизация: `parse_intent` → `nlu.py`, enum'ы вместо строк, try/except с fallback-ответом, логирование без PII, тесты перенесены в `tests/`. 54 теста. Статус: готово.
- Итерация 6 — переход на aliceio: Dispatcher/Router/FSM/Middleware; `nlu.py` (regex-парсер) и `states.py` удалены, NLU делегирован платформе; интенты save/find/list/delete заведены в консоли; main.py — 26 строк; DI YDB. 26 тестов. Статус: готово.
- Итерация 7 — расширение репозитория: `search_items`/`list_names`/`item_exists`; FIND с несколькими совпадениями; LIST только имён; SAVE с проверкой существования → FSM `awaiting_confirmation` («Обновить местоположение?»). 45 тестов. Статус: готово.
- Итерация 8 — нормализация «вещи»: `ItemRecord` dataclass, `normalize_thing()` как единственная точка decompose/canonicalize/canonical_key; протокол сокращён до 4 методов; коллизия canonical_key → `awaiting_confirmation`. 79 тестов. Статус: готово.
- Итерация 9 — адаптация YDB: таблица пересоздана c PK `(user_id, canonical_key)` и NOT NULL; SQL без `Unicode::ToLower`; `find_by_canonical_key` с LIMIT 1. Статус: готово.
- Итерация 9.5 — консолидация: репозитории собраны в пакет `src/db/` (protocol/memory/ydb/__init__), обновлены импорты. 89 тестов. Статус: готово.
- Итерация 10 — логирование: stdlib `logging` (StreamHandler/sys.stdout), NLU-логирование в intents/normalize/decomposer, PII-правило `user_id[:8]`, LOG_LEVEL через env. Тесты логирования. Статус: готово.

После журнала (по git-истории):

- Замена loguru обратно на stdlib logging (a8833dd → 2488044).
- JSON formatter для Yandex Cloud Logging, выравнивание со спецификацией платформы (97ce20e, a58467c).
- Рефакторинг decomposer: скоринговая модель выбора головы за 9 этапов (1ca9636).
- Внедрение OpenSpec: контекст перенесён в `openspec/project.md`, bootstrap спеков текущих возможностей, старые документы (PROJECT_INSTRUCTIONS.md, PROJECT_TREE.md) выведены из обращения.

## 11. Открытые вопросы

- Поддержка нескольких мест для одной вещи / истории перемещений?
- Нечёткий поиск при отсутствии точного совпадения (fuzzy)?
- Развёртывание в облаке и проверка грамматик интентов на реальных фразах (см. §5).

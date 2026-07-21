# Дерево проекта where_things

> Автоматически обновляемое описание структуры проекта.
> Последнее обновление: 2026-07-20

```
where_things/
├── main.py                          # Точка входа: Dispatcher + YCF webhook handler
├── AGENTS.md                        # Инструкции сборки, команды разработки
├── PROJECT_INSTRUCTIONS.md          # Полный контекст проекта, ADR, журнал итераций
├── PROJECT_TREE.md                  # Это дерево проекта
├── README.md
├── alice_intents_grammars.md        # Грамматики интентов для Yandex Dialogs консоли
├── pyproject.toml                   # Конфигурация ruff, правила, per-file-ignores
├── setup.cfg                        # Конфигурация flake8/WPS (расширение только с согласия владельца)
├── .python-version                  # Версия Python (3.12)
├── uv.lock                          # Lock файл зависимостей
├── .env.example                     # Пример переменных окружения
│
├── src/                             # Исходный код навыка
│   ├── __init__.py
│   ├── handlers.py                  # Обработчики интентов Alice + FSM + AuthMiddleware
│   │                                  handle_launch, handle_save, handle_confirmation,
│   │                                  handle_find, handle_list, handle_delete, handle_unknown
│   │
│   ├── db/                          # Пакет работы с базой данных
│   │   ├── __init__.py              # Ре-экспорты: ItemRecord, ItemsRepository, репозитории
│   │   ├── protocol.py              # ItemsRepository Protocol + dataclass ItemRecord
│   │   ├── memory.py                # InMemoryItemsRepository (тестовая реализация)
│   │   └── ydb.py                   # YdbItemsRepository (продакшн, YDB + YQL)
│   │                                  4 метода: upsert_item, find_by_canonical_key,
│   │                                  delete_item, list_display_names
│   │
│   └── nlu/                         # Пакет NLU (обработка естественного языка)
│       ├── __init__.py              # Ре-экспорты: intents + thing pipeline + normalize
│       ├── slots.py                 # get_intent(), get_slot() — извлечение данных из NLU
│       ├── intents.py               # SaveIntent, FindIntent, DeleteIntent — типизированные модели
│       │                              Содержат display_name + canonical_key (нормализация)
│       │                              Константы: INTENT_SAVE, INTENT_FIND, INTENT_DELETE
│       │
│       └── thing/                   # Конвейер нормализации сущности Thing
│           ├── __init__.py          # Ре-экспорты: decompose, canonicalize, canonical_key, normalize_thing
│           ├── decomposer.py        # Морфологический разбор pymorphy3
│           │                          DecomposeStatus, ThingDescriptor, DecomposeResult
│           │                          type NounInfo = tuple[str, str]
│           │                          _parse_tokens(), _build_descriptor(), _pick_head()
│           ├── canonical_dict.py    # Словарь канонизации (MappingProxyType)
│           ├── canonicalizer.py     # canonicalize() → CanonicalThing
│           ├── matcher.py           # canonical_key() — только построение ключа идентичности
│           └── normalize.py         # normalize_thing() → NormalizedThing (единая точка вызова)
│
├── tests/                           # Тесты
│   ├── __init__.py
│   ├── conftest.py                  # Общие фикстуры
│   ├── test_handler.py              # Юнит-тесты обработчиков (включая тесты нормализации)
│   ├── test_handler_manual.py       # CLI раннер для ручного тестирования
│   ├── test_runner.py               # Симулятор Cloud Functions с проверкой тайминга
│   ├── test_states_with_repo.py     # Интеграционные тесты с InMemoryRepo
│   ├── test_ydb.py                  # YDB интеграционные тесты (пропускаются без env)
│   │                                  no_ydb_env fixture для изоляции тестов
│   │
│   └── nlu/thing/                   # Тесты конвейера нормализации
│       ├── __init__.py
│       ├── test_decomposer.py       # Тесты: разбор + инварианты + _assert_ok_head helper
│       ├── test_canonicalizer.py    # Тесты: канонизация + идемпотентность
│       ├── test_matcher.py          # Тесты: canonical_key (формат ключа)
│       └── test_normalize.py        # Тесты: normalize_thing (OK/NO_HEAD/AMBIGUOUS_HEAD)
│
└── test_data/                       # JSON фикстуры для ручного/симуляторного тестирования
    ├── launch.json                  # Новый сеанс
    ├── save_item.json               # Сохранение вещи
    ├── save_multiword.json          # Сохранение многословной вещи
    ├── save_incomplete.json         # Неполное сохранение (без места)
    ├── find_item.json               # Поиск вещи
    ├── find_unknown.json            # Поиск неизвестной вещи
    ├── list_items.json              # Список всех вещей
    ├── delete_item.json             # Удаление вещи
    └── awaiting_place_*.json        # FSM состояния (ожидание подтверждения)
```

## Архитектурный поток зависимостей

```
main.py → handlers.py → nlu/intents.py → slots.py → message.nlu.intents
                    │                   → thing/normalize.py → decompose → canonicalize → canonical_key
                    └→ db/protocol.py → db/memory.py | db/ydb.py
```

## Ключевые решения (ADR)

| Решение | Описание |
|---------|----------|
| Intent parsing | Делегирован Yandex Dialogs платформе, код читает `message.nlu.intents` |
| Идентичность вещи | `canonical_key` — точное совпадение canonical_head#sorted(modifiers) |
| Нормализация | `normalize_thing()` — единственная точка вызова, в `intents.py` |
| Канонизация | Словарь-мэппер `canonical_dict.py`, тотальная функция |
| Морфология | pymorphy3, без тяжёлых NLP-моделей (Natasha, spaCy) |
| Поиск | Exact match через `find_by_canonical_key`, без fuzzy |
| Хранилище | Protocol (db/protocol.py) + 2 реализации (db/memory.py + db/ydb.py) |
| Коллизия canonical_key | Всегда `awaiting_confirmation` (обновление display_name) |

## Статистика

| Метрика | Значение |
|---------|----------|
| Модули src/ | 12 файлов (включая nlu/ и db/) |
| Тесты | 89 тестов (81 passed, 8 skipped) |
| thing/ тесты | 35 тестов |
| Зависимости | ydb, aliceio, pymorphy3 |

# Дерево проекта where_things

> Автоматически обновляемое описание структуры проекта.
> Последнее обновление: 2026-07-19

```
where_things/
├── main.py                          # Точка входа: Dispatcher + YCF webhook handler
├── AGENTS.md                        # Инструкции сборки, команды разработки
├── PROJECT_INSTRUCTIONS.md          # Полный контекст проекта, ADR, журнал итераций
├── README.md
├── alice_intents_grammars.md        # Грамматики интентов для Yandex Dialogs консоли
├── pyproject.toml                   # Конфигурация ruff, правила, per-file-ignores
├── setup.cfg                        # Конфигурация flake8/WPS
├── .python-version                  # Версия Python (3.12)
├── uv.lock                          # Lock файл зависимостей
├── .env.example                     # Пример переменных окружения
│
├── src/                             # Исходный код навыка
│   ├── __init__.py
│   ├── handlers.py                  # Обработчики интентов Alice + FSM + AuthMiddleware
│   │                                  handle_launch, handle_save, handle_confirmation,
│   │                                  handle_find, handle_list, handle_delete, handle_unknown
│   ├── repository.py                # ItemsRepository Protocol (интерфейс хранилища)
│   ├── memory_repository.py         # InMemoryItemsRepository (тестовая реализация)
│   ├── ydb_repository.py            # YdbItemsRepository (продакшн, YDB + SQL)
│   │
│   └── nlu/                         # Пакет NLU (обработка естественного языка)
│       ├── __init__.py              # Ре-экспорты: intents + thing pipeline
│       ├── slots.py                 # get_intent(), get_slot() — извлечение данных из NLU
│       ├── intents.py               # SaveIntent, FindIntent, DeleteIntent — типизированные модели
│       │
│       └── thing/                   # Конвейер нормализации сущности Thing
│           ├── __init__.py          # Ре-экспорты: decompose, canonicalize, canonical_key, match
│           ├── decomposer.py        # Морфологический разбор pymorphy3
│           │                          DecomposeStatus, ThingDescriptor, DecomposeResult
│           ├── canonical_dict.py    # Словарь канонизации (синонимы: смартфон→телефон)
│           ├── canonicalizer.py     # canonicalize() → CanonicalThing
│           └── matcher.py           # canonical_key(), match() + scoring (overlap coefficient)
│                                      SearchResult, MODIFIER_WEIGHT_*
│
├── tests/                           # Тесты
│   ├── __init__.py
│   ├── conftest.py                  # Общие фикстуры
│   ├── test_handler.py              # Юнит-тесты обработчиков (23 теста)
│   ├── test_handler_manual.py       # CLI раннер для ручного тестирования
│   ├── test_runner.py               # Симулятор Cloud Functions с проверкой тайминга
│   ├── test_states_with_repo.py     # Интеграционные тесты с InMemoryRepo (13 тестов)
│   ├── test_ydb.py                  # YDB интеграционные тесты (пропускаются без env)
│   │
│   └── nlu/thing/                   # Тесты конвейера нормализации (30 тестов)
│       ├── __init__.py
│       ├── test_decomposer.py       # 17 тестов: разбор + инварианты
│       ├── test_canonicalizer.py    # 6 тестов: канонизация + идемпотентность
│       └── test_matcher.py          # 7 тестов: exact/ambiguous/empty matching
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
                    ├→ nlu/thing/decomposer.py → canonicalizer.py → matcher.py
                    └→ repository.py → ydb_repository.py | memory_repository.py
```

## Ключевые решения (ADR)

| Решение | Описание |
|---------|----------|
| Intent parsing | Делегирован Yandex Dialogs платформе, код читает `message.nlu.intents` |
| Идентичность вещи | `canonical_key` — точное совпадение canonical_head#sorted(modifiers) |
| Канонизация | Словарь-мэппер `canonical_dict.py`, тотальная функция |
| Морфология | pymorphy3, без тяжёлых NLP-моделей (Natasha, spaCy) |
| Поиск | Exact match через canonical_key, без полнотекстового индекса |
| Хранилище | Protocol (ItemsRepository) + 2 реализации (InMemory + YDB) |

## Статистика

| Метрика | Значение |
|---------|----------|
| Модули src/ | 8 файлов |
| Тесты | 54 теста (46 passed, 8 skipped) |
| thing/ тесты | 30 тестов |
| Зависимости | ydb, aliceio, pymorphy3 |

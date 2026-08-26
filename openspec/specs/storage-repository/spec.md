# storage-repository Specification

## Purpose

Хранение пар (вещь, место) пользователей: контракт `ItemsRepository` (Protocol)
с двумя реализациями — InMemory для тестов и YDB serverless для продакшна.
Ключ записи — `(user_id, canonical_key)`.

## Requirements

### Requirement: Контракт ItemsRepository

Хранилище SHALL предоставлять четыре операции: `upsert_item` (вставка или
обновление), `find_by_canonical_key` (возвращает ItemRecord или None),
`delete_item` (удаление без ошибки при отсутствии записи),
`list_display_names` (список имён пользователя).

#### Scenario: Полный жизненный цикл записи

```gherkin
Допустим хранилище пользователя пусто
Когда вещь сохраняется методом upsert_item
Тогда find_by_canonical_key возвращает запись с location и verb
Когда та же запись обновляется upsert_item с новым местом
Тогда find_by_canonical_key возвращает новое место
Когда delete_item удаляет запись
Тогда find_by_canonical_key возвращает None
И list_display_names не содержит имя вещи
```

*Трассировка: `tests/test_states_with_repo.py::TestInMemoryRepository`, `src/db/protocol.py`*

#### Scenario: Мягкое удаление отсутствующей записи

```gherkin
Допустим записи с таким canonical_key нет
Когда вызывается delete_item
Тогда операция завершается без исключения
```

*Трассировка: `tests/test_states_with_repo.py::TestInMemoryRepository::test_delete_nonexistent`*

### Requirement: Данные изолированы по пользователю

Все операции SHALL ограничиваться записями данного `user_id`: один пользователь
SHALL NOT видеть или изменять вещи другого.

#### Scenario: Разные пользователи не пересекаются

```gherkin
Допустим два разных user_id сохранили вещи
Когда первый пользователь запрашивает список или поиск
Тогда возвращаются только его собственные записи
```

*Трассировка: `src/db/protocol.py` (user_id — первый параметр всех методов)*

### Requirement: InMemory-реализация эквивалентна по контракту

InMemoryItemsRepository SHALL удовлетворять протоколу полностью и использоваться
как фейк в тестах, чтобы юнит-тесты не требовали YDB.

#### Scenario: Замена прод-хранилища в тестах

```gherkin
Допустим тест создаёт InMemoryItemsRepository
Когда через него прогоняются сценарии save/find/list/delete
Тогда поведение совпадает с контрактом ItemsRepository без сетевых вызовов
```

*Трассировка: `tests/test_states_with_repo.py::TestStatesWithInMemory`, `src/db/memory.py`*

### Requirement: YDB-реализация поверх таблицы items

YdbItemsRepository SHALL работать с таблицей `items` c PK `(user_id, canonical_key)`
и NOT NULL полями `user_id/canonical_key/display_name/location`; поиск SHALL
использовать LIMIT 1 без серверного приведения регистра (нормализация ключа —
обязанность NLU-конвейера).

#### Scenario: Интеграционная проверка против реальной базы

```gherkin
Допустим заданы переменные окружения подключения к YDB
Когда запускается интеграционный тест
Тогда соединение, схема таблицы и CRUD-операции проходят против реальной базы
```

*Трассировка: `tests/test_ydb.py` (skipped без env), `src/db/ydb.py`*

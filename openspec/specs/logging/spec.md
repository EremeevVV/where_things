# logging Specification

## Purpose

Диагностическое журналирование навыка: структурные JSON-логи для Yandex Cloud
Logging через stdout, настраиваемый уровень, логирование NLU-решений и правило
безопасности персональных данных.

## Requirements

### Requirement: JSON-формат записей для Yandex Cloud Logging

Каждая запись SHALL сериализоваться в JSON с обязательными полями `message`
(текст) и `level`; уровень SHALL маппиться в шкалу платформы: WARNING → WARN,
CRITICAL → FATAL, остальные уровни передаются как есть.

#### Scenario: Стандартная запись

```gherkin
Допустим корневой логгер настроен с JsonFormatter
Когда модуль пишет запись уровня INFO или WARNING
Тогда stdout получает JSON со полями message, level, logger
И уровень WARNING сериализуется как WARN
```

*Трассировка: `main.py::JsonFormatter`*

#### Scenario: Запись с исключением

```gherkin
Допустим логируется исключение с traceback
Когда JsonFormatter форматирует запись
Тогда JSON содержит поле exception с текстом traceback
```

*Трассировка: `main.py::JsonFormatter::formatException`*

### Requirement: Уровень логирования из окружения

Уровень SHALL задаваться переменной `LOG_LEVEL` со значением по умолчанию INFO;
вывод направляется в stdout (единственный канал Cloud Functions).

#### Scenario: Отладочный уровень в тестах

```gherkin
Допустим переменная LOG_LEVEL установлена в DEBUG или WARNING
Когда запускается тестовый набор
Тогда подробность логирования соответствует значению переменной
```

*Трассировка: `main.py` (logging setup), AGENTS.md § Local testing*

### Requirement: Без персональных данных

В логах SHALL NOT появляться полный `user_id`: разрешён только префикс
`user_id[:8]`. Названия вещей и мест допускаются как предмет диагностики NLU.

#### Scenario: Логирование интента

```gherkin
Допустим приходит запрос с полным user_id
Когда хендлер логирует обработку интента
Тогда в записи присутствует не более 8 первых символов user_id
```

*Трассировка: `src/handlers.py`, `openspec/project.md` § История итераций (правило PII, итерация 10)*

### Requirement: Журналирование решений NLU

Конвейер NLU SHALL писать диагностические записи: INFO/WARNING при разборе
интентов и нормализации, DEBUG — детали декомпозиции; предупреждения SHALL
фиксировать деградации (NO_HEAD/AMBIGUOUS_HEAD) и отсутствие ожидаемых слотов.

#### Scenario: Предупреждение о деградации нормализации

```gherkin
Допустим разбор вещи завершился статусом NO_HEAD
Когда normalize_thing завершает работу
Тогда пишется WARNING-запись с причиной деградации
```

*Трассировка: `tests/test_nlu_logging.py`, `tests/nlu/thing/test_normalize.py::TestNormalizeLogging`*

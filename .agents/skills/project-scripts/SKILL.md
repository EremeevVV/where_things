---
name: project-scripts
description: Использование служебных скриптов проекта в папке scripts/ для сборки архива Yandex Cloud Functions, выгрузки файлов для внешней LLM и обновления дерева проекта в AGENTS.md.
---

# Служебные скрипты проекта (`scripts/`)

Используй соответствующие скрипты из `scripts/` в следующих сценариях:

1. **Подготовка архива для выгрузки на площадку (Yandex Cloud Functions)**
   - Когда пользователь просит подготовить архив / билд для деплоя на площадку Yandex Cloud:
   ```powershell
   .venv\Scripts\python.exe scripts/build_ycf_zip.py
   ```
   - Собирает `main.py`, `src/` и `requirements.txt` в `var/where_things.zip`.

2. **Подготовка файлов проекта для внешней LLM**
   - Когда нужно подготовить файлы проекта для обновления или анализа во внешней LLM:
   ```powershell
   .venv\Scripts\python.exe scripts/collect_for_external.py
   ```
   - Копирует исходники (`*.py`), спеки и документацию (`*.md`), конфиги (`*.toml`, `*.yaml`, `*.yml`, `*.txt`, `*.cfg`, `*.example`) и фикстуры (`*.json`) в `var/flatten/`, исключая `.env`, кэши, `.git`, `.venv`, `.opencode` и `var/`.

3. **Обновление дерева проекта в `AGENTS.md`**
   - Когда нужно обновить структуру/дерево проекта в `AGENTS.md`:
   ```powershell
   .venv\Scripts\python.exe scripts/project_tree.py
   ```
   - Выводит актуальное дерево проекта в stdout (опционально `--max-depth <N>` или `--output <путь>`).

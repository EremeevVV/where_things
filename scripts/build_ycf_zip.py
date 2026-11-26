from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

REQUIRED_FILES: tuple[str, ...] = ("main.py", "requirements.txt")
SRC_DIR_NAME = "src"
DEFAULT_ARCHIVE_NAME = "where_things.zip"
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"))
EXCLUDED_SUFFIXES: frozenset[str] = frozenset((".pyc", ".pyo"))
EXCLUDED_FILE_NAMES: frozenset[str] = frozenset((".DS_Store", "Thumbs.db"))
BYTES_PER_KB = 1024


def _should_include(file_path: Path, src_dir: Path) -> bool:
    """Return True if a file inside src/ should be packaged into the zip."""
    if not file_path.is_file():
        return False
    rel_parts = file_path.relative_to(src_dir).parts[:-1]
    if any(part in EXCLUDED_DIR_NAMES for part in rel_parts):
        return False
    if file_path.name in EXCLUDED_FILE_NAMES:
        return False
    return file_path.suffix not in EXCLUDED_SUFFIXES


def _collect_package_files(project_root: Path) -> list[Path]:
    """Collect main.py, requirements.txt, and all runtime files from src/."""
    collected: list[Path] = []
    for rel_name in REQUIRED_FILES:
        file_path = project_root / rel_name
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        collected.append(file_path)

    src_dir = project_root / SRC_DIR_NAME
    if not src_dir.is_dir():
        raise FileNotFoundError(src_dir)

    src_files = [path for path in src_dir.rglob("*") if _should_include(path, src_dir)]
    collected.extend(sorted(src_files))
    return collected


def build_ycf_archive(project_root: Path, output_zip: Path) -> list[Path]:
    """Create a deployment zip archive for Yandex Cloud Functions."""
    resolved_root = project_root.resolve()
    files_to_pack = _collect_package_files(resolved_root)

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files_to_pack:
            arcname = file_path.relative_to(resolved_root).as_posix()
            archive.write(file_path, arcname=arcname)

    return files_to_pack


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    project_root = Path(__file__).resolve().parent.parent
    default_output = project_root / "var" / DEFAULT_ARCHIVE_NAME
    parser = argparse.ArgumentParser(
        description="Собрать zip-архив (main.py, src/, requirements.txt) для Yandex Cloud Functions.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=project_root,
        help="Корень проекта (по умолчанию корень репозитория).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=f"Путь к итоговому zip-архиву (по умолчанию var/{DEFAULT_ARCHIVE_NAME}).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for building the Yandex Cloud Functions zip archive."""
    args = _parse_args()
    packed = build_ycf_archive(args.root, args.output)
    size_kb = args.output.stat().st_size / BYTES_PER_KB
    sys.stdout.write(
        f"Архив создан: {args.output} ({len(packed)} файлов, {size_kb:.1f} КБ)\n",
    )


if __name__ == "__main__":
    main()

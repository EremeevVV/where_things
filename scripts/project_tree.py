from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXCLUDED_DIRS: frozenset[str] = frozenset(
    (
        ".air",
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "env",
        "node_modules",
        "var",
        "venv",
    ),
)

DEFAULT_EXCLUDED_FILES: frozenset[str] = frozenset(
    (
        ".DS_Store",
        ".env",
        "Thumbs.db",
    ),
)

DEFAULT_EXCLUDED_SUFFIXES: frozenset[str] = frozenset(
    (
        ".log",
        ".pyc",
        ".pyo",
        ".zip",
    ),
)

BRANCH_MID = "├── "
BRANCH_LAST = "└── "
INDENT_MID = "│   "
INDENT_LAST = "    "


@dataclass(frozen=True, slots=True)
class TreeOptions:
    """Configuration and helpers for directory tree traversal."""

    excluded_dirs: frozenset[str] = DEFAULT_EXCLUDED_DIRS
    max_depth: int | None = None

    def is_ignored(self, path: Path) -> bool:
        """Return True if the path should be excluded from the tree."""
        if path.is_dir():
            return path.name in self.excluded_dirs
        if path.name in DEFAULT_EXCLUDED_FILES:
            return True
        return path.suffix in DEFAULT_EXCLUDED_SUFFIXES

    def sort_key(self, path: Path) -> tuple[bool, str]:
        """Sort directories before files, alphabetically case-insensitive."""
        return (not path.is_dir(), path.name.lower())

    def format_entry(self, prefix: str, child: Path, *, is_last: bool) -> str:
        """Format a single tree line for a file or directory."""
        connector = BRANCH_LAST if is_last else BRANCH_MID
        suffix = "/" if child.is_dir() else ""
        return f"{prefix}{connector}{child.name}{suffix}"


def _walk_tree(
    directory: Path,
    prefix: str,
    lines: list[str],
    options: TreeOptions,
    depth: int = 0,
) -> None:
    """Recursively append formatted tree lines for a directory."""
    if options.max_depth is not None and depth >= options.max_depth:
        return

    children = sorted(
        (child for child in directory.iterdir() if not options.is_ignored(child)),
        key=options.sort_key,
    )

    for index, child in enumerate(children):
        is_last = index == len(children) - 1
        lines.append(options.format_entry(prefix, child, is_last=is_last))
        if child.is_dir():
            indent = INDENT_LAST if is_last else INDENT_MID
            _walk_tree(child, f"{prefix}{indent}", lines, options, depth + 1)


def build_tree(root: Path, max_depth: int | None = None) -> str:
    """Build an ASCII/UTF-8 directory tree string for the project root."""
    resolved = root.resolve()
    lines = [f"{resolved.name}/"]
    options = TreeOptions(max_depth=max_depth)
    _walk_tree(resolved, "", lines, options)
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Сформировать дерево проекта для обновления AGENTS.md.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=project_root,
        help="Корень проекта (по умолчанию корень репозитория).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Максимальная глубина обхода (по умолчанию без ограничений).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Необязательный путь к файлу для сохранения результата.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for generating the project tree."""
    args = _parse_args()
    tree_text = build_tree(args.root, max_depth=args.max_depth)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{tree_text}\n", encoding="utf-8")

    sys.stdout.write(f"{tree_text}\n")


if __name__ == "__main__":
    main()

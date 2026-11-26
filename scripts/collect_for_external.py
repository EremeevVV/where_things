from __future__ import annotations

import fnmatch
import shutil
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    (
        ".air",
        ".git",
        ".idea",
        ".mypy_cache",
        ".opencode",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "env",
        "node_modules",
        "scripts",
        "var",
        "venv",
    ),
)

DEFAULT_EXCLUDE_PATTERNS: frozenset[str] = frozenset(
    (
        ".env",
        "__init__.py",
        "*.lock",
        "*.log",
        "*.pyc",
        "*.pyo",
        "*.zip",
        "uv.lock",
    ),
)

DEFAULT_INCLUDE_EXTENSIONS: frozenset[str] = frozenset(
    (
        ".cfg",
        ".example",
        ".json",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    ),
)


@dataclass(frozen=True, slots=True)
class CollectConfig:
    """Configuration for collecting project files for an external LLM."""

    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS
    exclude_patterns: tuple[str, ...] = tuple(DEFAULT_EXCLUDE_PATTERNS)
    include_extensions: frozenset[str] = DEFAULT_INCLUDE_EXTENSIONS
    flatten: bool = True
    clean_dst: bool = True
    copy_func: Callable[[Path, Path], object] = shutil.copy2

    def matches_excluded_pattern(self, rel_path: Path) -> bool:
        """Return True if the path matches any excluded glob pattern."""
        rel_posix = rel_path.as_posix()
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(rel_path.name, pattern) or fnmatch.fnmatch(rel_posix, pattern):
                return True
        return False

    def is_included(self, file_path: Path, rel_path: Path) -> bool:
        """Return True if the file matches extensions and is not excluded."""
        if not file_path.is_file():
            return False
        if file_path.suffix.lower() not in self.include_extensions:
            return False
        if self.exclude_dirs.intersection(rel_path.parts[:-1]):
            return False
        return not self.matches_excluded_pattern(rel_path)


def _make_flat_target(dst_root: Path, src_file: Path) -> Path:
    """Pick a collision-free filename inside dst_root for flatten mode."""
    target = dst_root / src_file.name
    if not target.exists():
        return target

    parent_name = src_file.parent.name
    base_name = f"{src_file.stem}_{parent_name}"
    target = dst_root / f"{base_name}{src_file.suffix}"
    if not target.exists():
        return target

    index = 1
    while True:
        candidate = dst_root / f"{base_name}__{index}{src_file.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _copy_if_included(
    candidate: Path,
    src_path: Path,
    dst_path: Path,
    cfg: CollectConfig,
) -> Path | None:
    """Copy candidate to dst_path if it passes filters; otherwise return None."""
    if candidate.is_relative_to(dst_path):
        return None
    rel = candidate.relative_to(src_path)
    if not cfg.is_included(candidate, rel):
        return None

    target = _make_flat_target(dst_path, candidate) if cfg.flatten else dst_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    cfg.copy_func(candidate, target)
    return target


def _collect_loop(src_path: Path, dst_path: Path, cfg: CollectConfig) -> list[Path]:
    """Iterate over source tree and copy matching files."""
    copied: list[Path] = []
    for candidate in sorted(src_path.rglob("*")):
        target = _copy_if_included(candidate, src_path, dst_path, cfg)
        if target is not None:
            copied.append(target)
    return copied


def collect_project_files(
    src_root: str | Path,
    dst_root: str | Path,
    config: CollectConfig | None = None,
) -> list[Path]:
    """Collect project source, docs, specs, and config files for an external LLM."""
    cfg = config or CollectConfig()
    src_path = Path(src_root).resolve()
    dst_path = Path(dst_root).resolve()

    if not src_path.is_dir():
        raise NotADirectoryError(src_path)
    if src_path == dst_path:
        raise ValueError(dst_path)

    if cfg.clean_dst and dst_path.exists():
        shutil.rmtree(dst_path)
    dst_path.mkdir(parents=True, exist_ok=True)
    return _collect_loop(src_path, dst_path, cfg)


def collect_py_files(
    src_root: str | Path,
    dst_root: str | Path,
    exclude_dirs: Iterable[str] = DEFAULT_EXCLUDE_DIRS,
    exclude_patterns: Iterable[str] = DEFAULT_EXCLUDE_PATTERNS,
    *,
    flatten: bool = False,
) -> list[Path]:
    """Backward-compatible wrapper around collect_project_files."""
    cfg = CollectConfig(
        exclude_dirs=frozenset(exclude_dirs),
        exclude_patterns=tuple(exclude_patterns),
        flatten=flatten,
        clean_dst=False,
    )
    return collect_project_files(src_root, dst_root, cfg)


def main() -> None:
    """Entry point for collecting project files into var/flatten."""
    project_root = Path(__file__).resolve().parent.parent
    dst_root = project_root / "var" / "flatten"
    files = collect_project_files(project_root, dst_root)
    sys.stdout.write(f"Скопировано {len(files)} файлов в {dst_root}\n")
    for copied_file in files:
        sys.stdout.write(f"  {copied_file.name}\n")


if __name__ == "__main__":
    main()

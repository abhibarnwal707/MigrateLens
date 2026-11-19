"""Read-only repo access. Never executes, imports or installs anything from the target.

Repo contents are treated as data only.
"""

from __future__ import annotations

from pathlib import Path

MAX_TOTAL_BYTES = 5 * 1024 * 1024  # reject repos with more than 5 MB of text
MAX_FILE_BYTES = 256 * 1024  # per-file read cap
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".terraform",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache", "target", ".idea",
}  # fmt: skip


class RepoTooLarge(ValueError):
    pass


class UnsafePath(ValueError):
    pass


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\0" in fh.read(2048)
    except OSError:
        return True


def list_files(root: str | Path) -> list[str]:
    """Return sorted repo-relative paths of text files. Raises RepoTooLarge over the cap."""
    root = Path(root).resolve()
    out: list[str] = []
    total = 0
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.is_symlink() or not p.is_file() or _is_binary(p):
            continue
        total += p.stat().st_size
        if total > MAX_TOTAL_BYTES:
            raise RepoTooLarge(f"repo has more than {MAX_TOTAL_BYTES} bytes of text")
        out.append(rel.as_posix())
    return out


def read_file(root: str | Path, rel_path: str, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Read one text file inside root, size-capped. Blocks path traversal and symlinks."""
    root = Path(root).resolve()
    target = root / rel_path
    if target.is_symlink():
        raise UnsafePath(f"symlinks are not followed: {rel_path}")
    target = target.resolve()
    if root != target and root not in target.parents:
        raise UnsafePath(f"path escapes the repo: {rel_path}")
    if not target.is_file() or _is_binary(target):
        raise FileNotFoundError(rel_path)
    with target.open("rb") as fh:
        return fh.read(max_bytes).decode("utf-8", errors="replace")

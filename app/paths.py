"""Resolve user-supplied filesystem paths inside allowed roots."""
from __future__ import annotations

from pathlib import Path

from . import settings


class UnsafePathError(ValueError):
    """Raised when a path escapes its allowed root."""


def resolve_under(root: Path, user_path: str) -> Path:
    """Return an absolute path that is guaranteed to sit under ``root``.

    Relative paths are joined to ``root``. Absolute paths are accepted only
    when they resolve inside ``root``.
    """
    if not user_path or not str(user_path).strip():
        raise UnsafePathError("path must not be empty")
    raw = Path(user_path)
    root = root.resolve()
    candidate = (root / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(
            f"path '{user_path}' is outside allowed root '{root}'"
        ) from exc
    return candidate


def resolve_field_path(user_path: str) -> Path:
    return resolve_under(settings.file_field_root(), user_path)


def resolve_output_path(user_path: str) -> Path:
    return resolve_under(settings.file_output_root(), user_path)

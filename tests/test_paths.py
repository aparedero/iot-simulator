"""Filesystem sandbox tests."""
from pathlib import Path

import pytest

from app.paths import UnsafePathError, resolve_field_path, resolve_output_path, resolve_under


def test_relative_path_joins_root(tmp_path):
    target = resolve_under(tmp_path, "a/b.jsonl")
    assert target == (tmp_path / "a" / "b.jsonl").resolve()


def test_absolute_path_inside_root_ok(tmp_path):
    inner = tmp_path / "ok.txt"
    assert resolve_under(tmp_path, str(inner)) == inner.resolve()


def test_path_escape_rejected(tmp_path):
    with pytest.raises(UnsafePathError):
        resolve_under(tmp_path, "../secret")
    with pytest.raises(UnsafePathError):
        resolve_under(tmp_path, "/etc/passwd")


def test_empty_path_rejected(tmp_path):
    with pytest.raises(UnsafePathError):
        resolve_under(tmp_path, "")


def test_output_and_field_helpers_use_env(tmp_path, monkeypatch):
    monkeypatch.setenv("IOTSIM_FILE_OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("IOTSIM_FILE_FIELD_ROOT", str(tmp_path / "in"))
    (tmp_path / "out").mkdir()
    (tmp_path / "in").mkdir()
    assert resolve_output_path("x.jsonl").parent == (tmp_path / "out").resolve()
    assert resolve_field_path("locs.txt").parent == (tmp_path / "in").resolve()
    with pytest.raises(UnsafePathError):
        resolve_output_path(str(Path("/tmp/nope.jsonl")))

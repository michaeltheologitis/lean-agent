"""Tests for the Lean tools (subprocess mocked — no real Lean needed)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lean_agent import tools


def _project(tmp_path: Path) -> Path:
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.29.1\n", encoding="utf-8")
    return tmp_path


def _mock(monkeypatch, *, returncode, stdout="", stderr=""):
    def fake_run(cmd, cwd, text, capture_output, timeout, check):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr("lean_agent.tools.subprocess.run", fake_run)


def test_has_sorry():
    assert tools.has_sorry("by sorry")
    assert tools.has_sorry("  admit")
    assert not tools.has_sorry("by simp")
    assert not tools.has_sorry("sorryAx_is_part_of_a_name")


def test_project_root_walks_up(tmp_path):
    root = _project(tmp_path)
    deep = root / "a" / "b"
    deep.mkdir(parents=True)
    assert tools._project_root(deep / "x.lean") == root


def test_project_root_missing(tmp_path):
    with pytest.raises(ValueError):
        tools._project_root(tmp_path / "x.lean")


def test_compile_success(monkeypatch, tmp_path):
    root = _project(tmp_path)
    (root / "p.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
    _mock(monkeypatch, returncode=0, stdout="")
    assert "status: compiled successfully" in tools.compile_file(str(root / "p.lean"))


def test_compile_failed(monkeypatch, tmp_path):
    root = _project(tmp_path)
    (root / "p.lean").write_text("oops\n", encoding="utf-8")
    _mock(monkeypatch, returncode=1, stderr="error: unknown identifier\n")
    out = tools.compile_file(str(root / "p.lean"))
    assert "status: compile failed" in out and "unknown identifier" in out


def test_sorry_warning_flagged(monkeypatch, tmp_path):
    """The trap: a sorry file compiles (exit 0) with a backtick warning — must not read as
    clean success."""
    root = _project(tmp_path)
    (root / "p.lean").write_text("theorem t : True := by sorry\n", encoding="utf-8")
    _mock(monkeypatch, returncode=0, stdout="p.lean:1:8: warning: declaration uses `sorry`\n")
    out = tools.compile_file(str(root / "p.lean"))
    assert "compiled WITH sorry/admit" in out
    assert "status: compiled successfully" not in out


def test_write_and_check_writes_and_flags(monkeypatch, tmp_path):
    root = _project(tmp_path)
    work = root / "_work" / "p.lean"
    _mock(monkeypatch, returncode=0, stdout="p.lean:1:8: warning: declaration uses `sorry`\n")
    out = tools.write_and_check.forward(file_path=str(work), content="theorem t : True := by sorry\n")
    assert work.read_text(encoding="utf-8") == "theorem t : True := by sorry\n"
    assert "sorry" in out.lower()


def test_write_and_check_rejects_non_lean(tmp_path):
    out = tools.write_and_check.forward(file_path=str(tmp_path / "x.txt"), content="hi")
    assert "must be a .lean file" in out

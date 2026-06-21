"""Tests for the Lean tool surface (no real Lean needed — subprocess is mocked)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lean_agent import lean


def _fake_project(tmp_path: Path) -> Path:
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.29.1\n", encoding="utf-8")
    (tmp_path / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")
    (tmp_path / "Demo.lean").write_text("theorem easy : True := by sorry\n", encoding="utf-8")
    return tmp_path


def _mock_run(monkeypatch, *, returncode, stdout="", stderr=""):
    calls = []

    def fake_run(cmd, cwd, text, capture_output, timeout, check):
        calls.append((cmd, cwd, timeout))
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr("lean_agent.lean.subprocess.run", fake_run)
    return calls


def test_has_forbidden():
    assert lean.has_forbidden("by sorry")
    assert lean.has_forbidden("  admit")
    assert not lean.has_forbidden("by simp")
    # substrings inside identifiers are not flagged
    assert not lean.has_forbidden("sorryAxioms_are_fine_as_a_name")


def test_project_build_success(monkeypatch, tmp_path):
    root = _fake_project(tmp_path)
    calls = _mock_run(monkeypatch, returncode=0, stdout="Build completed successfully\n")
    result = lean.lean_check_compiles.forward(project_path=str(root))
    assert "status: compiled successfully" in result
    assert calls[0][0] == ["lake", "build"]


def test_one_file_compile_failed(monkeypatch, tmp_path):
    root = _fake_project(tmp_path)
    _mock_run(monkeypatch, returncode=1, stderr="error: unknown identifier\n")
    result = lean.lean_check_compiles.forward(project_path=str(root), file_path="Demo.lean")
    assert "status: compile failed" in result
    assert "unknown identifier" in result


def test_sorry_warning_is_flagged(monkeypatch, tmp_path):
    """The trap: a file with sorry compiles (exit 0) with a warning — must NOT read as
    a clean success."""
    root = _fake_project(tmp_path)
    # Real Lean format: backticks around sorry, emitted on stdout, exit code 0.
    _mock_run(monkeypatch, returncode=0,
              stdout="Demo.lean:1:8: warning: declaration uses `sorry`\n")
    result = lean.lean_check_compiles.forward(project_path=str(root), file_path="Demo.lean")
    assert "compiled WITH sorry/admit" in result
    assert "status: compiled successfully" not in result


def test_rejects_missing_project(tmp_path):
    with pytest.raises(ValueError):
        lean.lean_check_compiles.forward(project_path=str(tmp_path / "missing"))


def test_rejects_non_lean_file(tmp_path):
    root = _fake_project(tmp_path)
    (root / "notes.txt").write_text("not lean\n", encoding="utf-8")
    with pytest.raises(ValueError):
        lean.lean_check_compiles.forward(project_path=str(root), file_path="notes.txt")


def test_write_and_check_writes_and_flags_sorry(monkeypatch, tmp_path):
    root = _fake_project(tmp_path)
    work = root / "_work"
    work.mkdir()
    work_file = work / "p.lean"
    work_file.write_text("placeholder\n", encoding="utf-8")
    _mock_run(monkeypatch, returncode=0,
              stdout="p.lean:1:8: warning: declaration uses `sorry`\n")

    tool = lean.make_write_and_check(root, work_file)
    out = tool.forward(content="theorem t : True := by sorry\n")
    # the file was actually written
    assert "by sorry" in work_file.read_text(encoding="utf-8")
    # and the still-incomplete proof is flagged
    assert "sorry" in out.lower()
    assert "compiled WITH sorry/admit" in out

"""Tests for Lean compile-checking tools."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lean_agent.lean_tools import LEAN_TOOLS, lean_check_compiles


def _fake_lean_project(tmp_path: Path) -> Path:
    (tmp_path / "lean-toolchain").write_text(
        "leanprover/lean4:v4.30.0\n",
        encoding="utf-8",
    )
    (tmp_path / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")
    (tmp_path / "Demo.lean").write_text(
        "theorem easy : True := by\n  trivial\n",
        encoding="utf-8",
    )
    return tmp_path


def test_lean_tools_registered():
    assert [tool.name for tool in LEAN_TOOLS] == ["lean_check_compiles"]


def test_lean_check_compiles_project_build(monkeypatch, tmp_path):
    root = _fake_lean_project(tmp_path)
    calls = []

    def fake_run(cmd, cwd, text, capture_output, timeout, check):
        calls.append((cmd, cwd, text, capture_output, timeout, check))
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Build completed successfully\n",
            stderr="",
        )

    monkeypatch.setattr("lean_agent.lean_tools.subprocess.run", fake_run)

    result = lean_check_compiles.forward(project_path=str(root))

    assert "status: compiled successfully" in result
    assert calls == [(["lake", "build"], root.resolve(), True, True, 120, False)]


def test_lean_check_compiles_one_file(monkeypatch, tmp_path):
    root = _fake_lean_project(tmp_path)
    calls = []

    def fake_run(cmd, cwd, text, capture_output, timeout, check):
        calls.append((cmd, cwd, text, capture_output, timeout, check))
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout="",
            stderr="error: no goals to be solved\n",
        )

    monkeypatch.setattr("lean_agent.lean_tools.subprocess.run", fake_run)

    result = lean_check_compiles.forward(
        project_path=str(root),
        file_path="Demo.lean",
        timeout_seconds=5,
    )

    assert "status: compile failed" in result
    assert "error: no goals to be solved" in result
    assert calls == [
        (["lake", "env", "lean", "Demo.lean"], root.resolve(), True, True, 5, False)
    ]


def test_lean_check_compiles_rejects_missing_project(tmp_path):
    with pytest.raises(ValueError):
        lean_check_compiles.forward(project_path=str(tmp_path / "missing"))


def test_lean_check_compiles_rejects_non_lean_file(tmp_path):
    root = _fake_lean_project(tmp_path)
    (root / "notes.txt").write_text("not Lean\n", encoding="utf-8")

    with pytest.raises(ValueError):
        lean_check_compiles.forward(project_path=str(root), file_path="notes.txt")

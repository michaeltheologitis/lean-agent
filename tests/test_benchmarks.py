"""Tests for the benchmark loaders + the shared Problem mechanic."""

from __future__ import annotations

from pathlib import Path

from lean_agent import benchmarks
from lean_agent.benchmarks import Problem, load


def _project(tmp_path: Path) -> Path:
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.29.1\n", encoding="utf-8")
    return tmp_path


# --- loaders ------------------------------------------------------------------


def test_putnam_loads_and_parses():
    (p,) = load("putnam", names=["putnam_1962_a1"])
    assert "five points" in p.informal.lower()
    assert p.statement.startswith("theorem putnam_1962_a1")
    assert "sorry" not in p.statement
    assert p.benchmark == "putnam"


def test_minif2f_loads_and_strips_statement():
    probs = load("minif2f")
    assert len(probs) >= 10
    p = next(x for x in probs if x.name == "mathd_algebra_116")
    assert p.statement.startswith("theorem mathd_algebra_116")
    assert "sorry" not in p.statement and p.informal == ""


def test_smoke_loads():
    names = {p.name for p in load("smoke")}
    assert "smoke_true" in names


def test_unknown_benchmark_raises():
    import pytest
    with pytest.raises(ValueError):
        load("nope")


# --- shared Problem mechanic --------------------------------------------------


def test_prepare_and_prompt(tmp_path):
    project = _project(tmp_path)
    prob = Problem(name="t", benchmark="smoke", project=project,
                   stub="theorem t : True := by sorry\n", statement="theorem t : True")
    work_file = prob.prepare(project / "_work")
    assert work_file.read_text(encoding="utf-8") == "theorem t : True := by sorry\n"
    prompt = prob.prompt(work_file)
    assert "write_and_check" in prompt and str(work_file) in prompt


def test_grade_pass(monkeypatch, tmp_path):
    project = _project(tmp_path)
    wf = project / "_work" / "t.lean"
    wf.parent.mkdir()
    wf.write_text("theorem t : True := by trivial\n", encoding="utf-8")
    prob = Problem(name="t", benchmark="smoke", project=project, stub="",
                   statement="theorem t : True")
    monkeypatch.setattr(benchmarks, "compile_file", lambda *a, **k: "status: compiled successfully\n")
    g = prob.grade(wf)
    assert g["passed"] and g["reason"] == "ok" and not g["statement_changed"]


def test_grade_rejects_sorry_without_compiling(monkeypatch, tmp_path):
    project = _project(tmp_path)
    wf = project / "_work" / "t.lean"
    wf.parent.mkdir()
    wf.write_text("theorem t : True := by sorry\n", encoding="utf-8")
    prob = Problem(name="t", benchmark="smoke", project=project, stub="",
                   statement="theorem t : True")
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        return "status: compiled successfully"

    monkeypatch.setattr(benchmarks, "compile_file", boom)
    g = prob.grade(wf)
    assert not g["passed"] and "sorry" in g["reason"] and called["n"] == 0


def test_grade_flags_statement_changed(monkeypatch, tmp_path):
    project = _project(tmp_path)
    wf = project / "_work" / "t.lean"
    wf.parent.mkdir()
    wf.write_text("theorem t : False := by trivial\n", encoding="utf-8")
    prob = Problem(name="t", benchmark="smoke", project=project, stub="",
                   statement="theorem t : True")
    monkeypatch.setattr(benchmarks, "compile_file", lambda *a, **k: "status: compiled successfully\n")
    assert prob.grade(wf)["statement_changed"]

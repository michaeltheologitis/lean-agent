"""Tests for the benchmark adapters + the shared Problem mechanic."""

from __future__ import annotations

from pathlib import Path

from lean_agent import benchmarks
from lean_agent.benchmarks import Problem, minif2f, putnam, smoke


class _FakeCompile:
    """Stand-in for the lean_check_compiles tool used by Problem.grade."""
    def __init__(self, out: str):
        self.out = out

    def forward(self, *a, **k) -> str:
        return self.out


def _fake_project(tmp_path: Path) -> Path:
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.29.1\n", encoding="utf-8")
    return tmp_path


# --- loaders ------------------------------------------------------------------


def test_putnam_loads_proof_only_by_default():
    probs = putnam.load(names=["putnam_1962_a1", "putnam_1962_a2", "putnam_1962_a5"])
    names = {p.name for p in probs}
    # a1 is proof-only; a2/a5 are answer_proof (have ..._solution := sorry) → filtered out
    assert "putnam_1962_a1" in names
    assert "putnam_1962_a2" not in names and "putnam_1962_a5" not in names


def test_putnam_answer_proof_when_requested():
    probs = putnam.load(names=["putnam_1962_a2"], task_type="answer_proof")
    assert [p.name for p in probs] == ["putnam_1962_a2"]


def test_putnam_parses_informal_and_statement():
    (p,) = putnam.load(names=["putnam_1962_a1"])
    assert "five points" in p.informal.lower()
    assert p.formal_statement.startswith("theorem putnam_1962_a1")
    assert "sorry" not in p.formal_statement
    assert p.benchmark == "putnam"


def test_putnam_years_filter():
    probs = putnam.load(years=(1962, 1962))
    assert probs and all(p.name.startswith("putnam_1962") for p in probs)


def test_minif2f_loads_and_strips_statement():
    probs = minif2f.load()
    assert len(probs) >= 10
    p = next(x for x in probs if x.name == "mathd_algebra_116")
    assert p.formal_statement.startswith("theorem mathd_algebra_116")
    assert "sorry" not in p.formal_statement
    assert p.informal == ""


def test_smoke_loads():
    probs = smoke.load()
    names = {p.name for p in probs}
    assert "smoke_true" in names
    assert all(p.benchmark == "smoke" for p in probs)


# --- shared Problem mechanic --------------------------------------------------


def test_prepare_and_build_prompt(tmp_path):
    project = _fake_project(tmp_path)
    work = project / "_work"
    prob = Problem(name="t", benchmark="smoke", project=project,
                   stub_text="theorem t : True := by sorry\n",
                   formal_statement="theorem t : True")
    work_file = prob.prepare(work)
    assert work_file.read_text(encoding="utf-8") == "theorem t : True := by sorry\n"
    prompt = prob.build_prompt(work_file)
    assert "_work/t.lean" in prompt
    assert "write_and_check" in prompt


def test_grade_pass(monkeypatch, tmp_path):
    project = _fake_project(tmp_path)
    work_file = project / "_work" / "t.lean"
    work_file.parent.mkdir()
    work_file.write_text("theorem t : True := by trivial\n", encoding="utf-8")
    prob = Problem(name="t", benchmark="smoke", project=project, stub_text="",
                   formal_statement="theorem t : True")
    monkeypatch.setattr(benchmarks, "lean_check_compiles",
                        _FakeCompile("status: compiled successfully\n"))
    g = prob.grade(work_file)
    assert g.passed and g.reason == "ok" and not g.statement_changed


def test_grade_rejects_sorry_without_compiling(monkeypatch, tmp_path):
    project = _fake_project(tmp_path)
    work_file = project / "_work" / "t.lean"
    work_file.parent.mkdir()
    work_file.write_text("theorem t : True := by sorry\n", encoding="utf-8")
    prob = Problem(name="t", benchmark="smoke", project=project, stub_text="",
                   formal_statement="theorem t : True")
    # compile would "succeed" — but has_forbidden short-circuits before we ever call it
    called = {"n": 0}

    class _Boom:
        def forward(self, *a, **k):
            called["n"] += 1
            return "status: compiled successfully"

    monkeypatch.setattr(benchmarks, "lean_check_compiles", _Boom())
    g = prob.grade(work_file)
    assert not g.passed and "sorry" in g.reason
    assert called["n"] == 0


def test_grade_flags_statement_changed(monkeypatch, tmp_path):
    project = _fake_project(tmp_path)
    work_file = project / "_work" / "t.lean"
    work_file.parent.mkdir()
    work_file.write_text("theorem t : False := by trivial\n", encoding="utf-8")
    prob = Problem(name="t", benchmark="smoke", project=project, stub_text="",
                   formal_statement="theorem t : True")
    monkeypatch.setattr(benchmarks, "lean_check_compiles",
                        _FakeCompile("status: compiled successfully\n"))
    g = prob.grade(work_file)
    assert g.statement_changed  # the original `theorem t : True` is gone

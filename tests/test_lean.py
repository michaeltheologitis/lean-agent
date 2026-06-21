"""Tests for the Lean backend: structured results + the lean_check tool (no real REPL)."""

from __future__ import annotations

from lean_agent.lean import LeanResult, make_lean_check


class _Msg:
    def __init__(self, data):
        self.data = data


class _Sorry:
    def __init__(self, goal):
        self.goal = goal


class _Resp:
    """Stands in for a LeanInteract CommandResponse."""
    def __init__(self, errors=(), sorries=()):
        self._errors = [_Msg(e) for e in errors]
        self.sorries = [_Sorry(g) for g in sorries]

    def get_errors(self):
        return self._errors


# --- LeanResult.from_response -------------------------------------------------


def test_result_valid():
    r = LeanResult.from_response(_Resp())
    assert r.ok and r.complete and "valid" in r.feedback


def test_result_errors():
    r = LeanResult.from_response(_Resp(errors=["unknown identifier 'foo'"]))
    assert not r.ok and "errors" in r.feedback and "foo" in r.feedback


def test_result_incomplete_sorry():
    r = LeanResult.from_response(_Resp(sorries=["n : Nat\n⊢ n = n"]))
    assert not r.ok and not r.complete
    assert "incomplete" in r.feedback and "⊢ n = n" in r.feedback


# --- make_lean_check ----------------------------------------------------------


class _FakeLean:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def check(self, code, env):
        self.calls.append(code)
        return self.result


def test_lean_check_records_pass_when_valid_and_on_target():
    lean = _FakeLean(LeanResult(ok=True, complete=True, feedback="✓ valid"))
    record = {"passed": False}
    tool = make_lean_check(lean, None, "theorem target : True", record)
    out = tool.forward(code="theorem target : True := trivial")
    assert "valid" in out
    assert record["passed"] is True
    assert lean.calls == ["theorem target : True := trivial"]


def test_lean_check_no_pass_if_statement_changed():
    lean = _FakeLean(LeanResult(ok=True, complete=True, feedback="✓ valid"))
    record = {"passed": False}
    tool = make_lean_check(lean, None, "theorem target : True", record)
    # valid, but it proved a different statement → not a pass
    tool.forward(code="theorem other : False → True := fun h => h.elim")
    assert record["passed"] is False


def test_lean_check_no_pass_if_not_ok():
    lean = _FakeLean(LeanResult(ok=False, complete=False, feedback="△ incomplete"))
    record = {"passed": False}
    tool = make_lean_check(lean, None, "theorem target : True", record)
    tool.forward(code="theorem target : True := by sorry")
    assert record["passed"] is False

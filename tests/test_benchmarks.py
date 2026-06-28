"""Tests for the benchmarks harness: the preamble/statement split + loaders + prompt."""

from __future__ import annotations

import pytest

from benchmarks import _split, load, load_experiment
from lean_agent import Problem
from lean_agent.agent import _prompt, _system_prompt


def test_split_single_theorem():
    text = "import Mathlib\nopen Nat\n\ntheorem foo (n : Nat) : n = n := by sorry\n"
    preamble, statement, name = _split(text)
    assert preamble == "import Mathlib\nopen Nat"
    assert statement == "theorem foo (n : Nat) : n = n"
    assert name == "foo"


def test_split_target_is_last_theorem():
    """Helper lemmas above the goal belong to the preamble; the goal is the last theorem."""
    text = (
        "def IsEven (n : Nat) : Prop := ∃ k, n = 2 * k\n\n"
        "theorem helper (n : Nat) : IsEven (n + n) := ⟨n, by omega⟩\n\n"
        "theorem target (n : Nat) : IsEven (n + n) := sorry\n"
    )
    preamble, statement, name = _split(text)
    assert "def IsEven" in preamble and "theorem helper" in preamble
    assert statement == "theorem target (n : Nat) : IsEven (n + n)"
    assert name == "target"


def test_split_strips_comments_from_preamble():
    text = "import Mathlib\n\n/-- doc -/\n-- a line comment\ntheorem foo : True := sorry\n"
    preamble, statement, _ = _split(text)
    assert preamble == "import Mathlib"
    assert statement == "theorem foo : True"


def test_load_minif2f():
    probs = load("minif2f")
    assert len(probs) == 3
    p = next(x for x in probs if x.name == "mathd_algebra_116")
    assert "import Mathlib" in p.preamble
    assert p.statement.startswith("theorem mathd_algebra_116") and "sorry" not in p.statement


def test_load_smoke_has_empty_preamble():
    p = next(x for x in load("smoke") if x.name == "smoke_true")
    assert p.preamble == ""  # core Lean, nothing to pre-load
    assert p.statement.startswith("theorem smoke_true")


def test_load_unknown_raises():
    with pytest.raises(ValueError):
        load("nope")


def test_load_experiment_conditions():
    probs = load_experiment("even_self")
    names = {p.name for p in probs}
    assert names == {"even_self/notated", "even_self/raw"}
    notated = next(p for p in probs if p.name == "even_self/notated")
    assert "def IsEven" in notated.preamble and "isEven_add_self" in notated.preamble
    raw = next(p for p in probs if p.name == "even_self/raw")
    assert raw.preamble == "" and raw.statement.startswith("theorem target")


# --- prompt building (core; uses a loaded Problem) ----------------------------


def test_prompt_mentions_tool_and_goal():
    (p,) = load_experiment("even_self", names=["raw"])
    prompt = _prompt(p)
    assert "lean_check" in prompt and "∃ k, n + n = 2 * k" in prompt


def test_system_prompt_includes_preamble_definitions():
    notated = Problem(name="t", benchmark="experiment",
                      preamble="def IsEven (n : Nat) : Prop := ∃ k, n = 2 * k", statement="theorem t : True")
    raw = Problem(name="t", benchmark="experiment", preamble="", statement="theorem t : True")
    assert "def IsEven" in _system_prompt(notated)
    assert "Already loaded" not in _system_prompt(raw)  # no preamble → no extra block


def test_system_prompt_appends_extra_instructions():
    p = Problem(name="t", benchmark="experiment", preamble="", statement="theorem t : True")
    out = _system_prompt(p, extra_instructions="You do NOT have Mathlib available.")
    assert "You do NOT have Mathlib available." in out


def test_system_prompt_no_extra_block_by_default():
    p = Problem(name="t", benchmark="experiment", preamble="", statement="theorem t : True")
    assert _system_prompt(p) == _system_prompt(p, "")

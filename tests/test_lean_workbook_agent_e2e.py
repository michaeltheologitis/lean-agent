"""End-to-end test for solving a small Mathlib Lean problem."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from smolagents import CodeAgent, OpenAIServerModel

from lean_agent import LEAN_TOOLS
from lean_agent import settings as settings_module
from lean_agent.lean_tools import lean_check_compiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEAN_PROJECT = PROJECT_ROOT / "lean_project"
PROBLEM_PATH = LEAN_PROJECT / "Problems" / "LeanWorkbookPlus2.lean"
SCRATCH_PATH = LEAN_PROJECT / "AgentOutput.lean"


pytestmark = pytest.mark.skipif(
    settings_module.get_settings().api_key is None,
    reason="model API key not set",
)


def _extract_candidate_code(answer: object) -> str:
    text = str(answer).strip()
    fenced = re.search(r"```(?:lean|lean4)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text


def _indent_proof(proof: str) -> str:
    lines = proof.strip().splitlines()
    return "\n".join("  " + line if line.strip() else line for line in lines)


def _source_from_answer(problem_source: str, answer: object) -> str:
    code = _extract_candidate_code(answer)
    forbidden = re.compile(r"\b(sorry|admit|axiom)\b")
    assert not forbidden.search(code), f"agent returned an unfinished/unsound proof:\n{code}"

    if "theorem lean_workbook_plus_2" in code:
        return code if "import Mathlib" in code else "import Mathlib\n\n" + code

    replacement = code if code.startswith("by") else "by\n" + _indent_proof(code)
    return problem_source.replace("by\n  sorry", replacement)


def test_agent_solves_lean_workbook_plus_2():
    if not LEAN_PROJECT.exists():
        pytest.skip("benchmark Lean project not found")

    problem_source = PROBLEM_PATH.read_text(encoding="utf-8")
    settings = settings_module.get_settings()
    model = OpenAIServerModel(
        model_id=settings.model_id,
        api_key=settings.api_key,
        api_base=settings.api_base,
        client_kwargs={"timeout": 90},
        temperature=0,
    )
    agent = CodeAgent(
        tools=LEAN_TOOLS,
        model=model,
        max_steps=6,
        instructions=(
            "You solve Lean 4 theorem-proving tasks. Return only the Lean proof "
            "replacing the sorry; no prose. Do not return sorry, admit, or axioms. "
            "The test harness will compile-check your final answer."
        ),
    )

    SCRATCH_PATH.write_text(problem_source, encoding="utf-8")
    try:
        answer = agent.run(
            "The following Lean file has one sorry. Replace the sorry with a complete proof.\n\n"
            f"Project path: {LEAN_PROJECT}\n"
            f"Problem file: {SCRATCH_PATH.relative_to(LEAN_PROJECT)}\n\n"
            "Lean file:\n"
            "```lean\n"
            f"{problem_source}"
            "```\n\n"
            "Return only the proof term or tactic block that replaces the sorry. "
            "A good approach is to rewrite membership in Set.Ioo, split the "
            "biconditional, and let nlinarith close the arithmetic goals."
        )

        candidate_source = _source_from_answer(problem_source, answer)
        SCRATCH_PATH.write_text(candidate_source, encoding="utf-8")
        result = lean_check_compiles.forward(
            str(LEAN_PROJECT),
            str(SCRATCH_PATH.relative_to(LEAN_PROJECT)),
            120,
        )
        assert "status: compiled successfully" in result, result
    finally:
        if os.getenv("KEEP_AGENT_LEAN_OUTPUT") != "1":
            SCRATCH_PATH.unlink(missing_ok=True)

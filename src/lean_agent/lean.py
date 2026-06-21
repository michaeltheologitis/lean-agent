"""Lean backend — the agent proves against a pre-warmed REPL environment (via LeanInteract).

The hypothesis this harness exists to test: Lean reasoning is more effective for an agent when
concepts are given as well-structured definitions/abstractions. So the central object is a
**pre-warmed environment**: a `preamble` (imports + the student's definitions/lemmas) is run
once to build a base environment, and every proof attempt runs *in* that environment — the
definitions are in scope. The same preamble is also put into the agent's system prompt
(in `agent.solve`), so both Lean and the LLM are "pre-warmed" with the concepts.

Unlike a `lake env lean` subprocess, the REPL is stateful (the base env persists across calls,
so Mathlib is imported once) and returns **structured** results — errors, sorries, and goal
states — so there's no regex for `sorry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lean_interact import Command, LeanREPLConfig, LeanServer, LocalProject, TempRequireProject
from smolagents import tool

from .settings import PROJECT_ROOT, get_settings

# Where each benchmark's matching built Lean project lives (gitignored sibling checkouts).
_BENCH_PROJECTS = {
    "minif2f": PROJECT_ROOT / "miniF2F-lean4",
    "putnam": PROJECT_ROOT / "PutnamBench" / "lean4",
}


def lean_config(benchmark: str, preamble: str) -> LeanREPLConfig:
    """Pick the LeanInteract config for a run. Core Lean (no Mathlib) just needs a version;
    a Mathlib task needs a built Mathlib project — the benchmark's sibling checkout, the
    configured `LEAN_PROJECT`, or a temp Mathlib project built on demand."""
    s = get_settings()
    if "import Mathlib" not in preamble:
        return LeanREPLConfig(lean_version=s.lean_version)
    project = _BENCH_PROJECTS.get(benchmark)
    if project is None and s.lean_project:
        project = Path(s.lean_project)
    if project is not None:
        return LeanREPLConfig(project=LocalProject(directory=str(project)))
    return LeanREPLConfig(project=TempRequireProject(lean_version=s.lean_version, require="mathlib"))


@dataclass
class LeanResult:
    ok: bool            # no errors AND no sorries — a complete, valid proof
    complete: bool      # no sorries
    feedback: str       # readable result for the agent + logs

    @classmethod
    def from_response(cls, resp) -> "LeanResult":
        errors = [m.data for m in resp.get_errors()]
        goals = [s.goal for s in getattr(resp, "sorries", [])]
        complete = not goals
        ok = not errors and complete
        if errors:
            feedback = "✗ errors:\n" + "\n".join(errors)
        elif not complete:
            feedback = ("△ no errors, but the proof is incomplete (`sorry`). Remaining goal(s):\n"
                        + "\n\n".join(goals))
        else:
            feedback = "✓ valid — the proof compiles with no errors and no `sorry`."
        return cls(ok=ok, complete=complete, feedback=feedback)


class Lean:
    """A LeanInteract REPL session. Build a pre-warmed base env from a preamble, then `check`
    code against it. One `Lean` is shared across all problems of a run (same project)."""

    def __init__(self, config: LeanREPLConfig):
        self.server = LeanServer(config)

    def base_env(self, preamble: str):
        """Run the preamble once; return the base environment id (None if the preamble is
        empty — checks then run in a fresh session). Raises if the preamble itself fails."""
        preamble = preamble.strip()
        if not preamble:
            return None
        resp = self.server.run(Command(cmd=preamble))
        if resp.has_errors():
            raise RuntimeError(
                "preamble failed to compile:\n" + "\n".join(m.data for m in resp.get_errors())
            )
        return resp.env

    def check(self, code: str, env) -> LeanResult:
        return LeanResult.from_response(self.server.run(Command(cmd=code, env=env)))


def make_lean_check(lean: Lean, env, statement: str, record: dict):
    """Build the agent's `lean_check` tool, bound to one problem's base env + target statement.

    Sets `record["passed"] = True` the first time a submission is a complete valid proof that
    still contains the target statement (so the agent can't 'win' by changing the goal)."""
    target = " ".join(statement.split())

    @tool
    def lean_check(code: str) -> str:
        """Compile Lean code against the pre-loaded environment and return the result.

        Args:
            code: a complete Lean declaration — the `theorem ... := <proof>` you are proving.
                Imports and any given definitions are ALREADY loaded; do not repeat them.
        """
        result = lean.check(code, env)
        if result.ok and target in " ".join(code.split()):
            record["passed"] = True
        return result.feedback

    return lean_check

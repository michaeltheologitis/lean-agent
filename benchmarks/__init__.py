"""Benchmarks — the evaluation harness (kept out of the core `lean_agent`).

A benchmark problem is a `.lean` file split into two parts:

  * **preamble** — everything before the target theorem: imports, `open`s, definitions, helper
    lemmas. Pre-loaded into the Lean environment AND the system prompt.
  * **statement** — the target `theorem <name> ... :=` (the goal; the agent supplies the proof).

The target is the **last** `theorem` in the file. `load(benchmark)` reads `smoke` / `minif2f` /
`putnam` from `benchmarks/data/<benchmark>/`.

For a one-off / hypothesis experiment, don't add a file — build a `Problem(...)` directly in
Python (preamble = your definitions, statement = the goal) and pass it to `solve`; the notebook
shows this. `PROJECTS` maps the Mathlib benchmarks to their matching built Lean project (a
gitignored sibling checkout); the runner passes it to `lean_config`.
"""

from __future__ import annotations

import re
from pathlib import Path

from lean_agent import Problem
from lean_agent.settings import PROJECT_ROOT

DATA = Path(__file__).resolve().parent / "data"
_THM_RE = re.compile(r"^theorem\s+(\w+)", re.MULTILINE)

# Mathlib benchmarks compile against a built sibling checkout at their own Mathlib version.
PROJECTS = {
    "minif2f": PROJECT_ROOT / "miniF2F-lean4",
    "putnam": PROJECT_ROOT / "PutnamBench" / "lean4",
}


def _informal(text: str, name: str) -> str:
    """The `/-- ... -/` docstring above the target theorem (PutnamBench has these); else ""."""
    m = re.search(r"/--(.*?)-/\s*\ntheorem " + re.escape(name), text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _split(text: str) -> tuple[str, str, str]:
    """Return (preamble, statement, name). Statement is the target theorem minus its
    `:= sorry` / `:= by sorry`. Preamble is everything above it, comments stripped."""
    matches = list(_THM_RE.finditer(text))
    if not matches:
        return text.strip(), "", ""
    m = matches[-1]
    name = m.group(1)
    preamble = re.sub(r"/--.*?-/", "", text[: m.start()], flags=re.DOTALL)
    preamble = re.sub(r"^[ \t]*--.*$", "", preamble, flags=re.MULTILINE).strip()
    block = text[m.start():].rstrip()
    if block.endswith("sorry"):
        block = block[: -len("sorry")].rstrip()
    if block.endswith("by"):
        block = block[: -len("by")].rstrip()
    if block.endswith(":="):
        block = block[:-2].rstrip()
    return preamble, block, name


def load(benchmark: str, *, names: list[str] | None = None) -> list[Problem]:
    """Load `smoke` / `minif2f` / `putnam` problems from `benchmarks/data/<benchmark>/`."""
    if benchmark not in ("smoke", "minif2f", "putnam"):
        raise ValueError(f"unknown benchmark {benchmark!r}")
    out: list[Problem] = []
    for f in sorted((DATA / benchmark).glob("*.lean")):
        if names and f.stem not in names:
            continue
        text = f.read_text(encoding="utf-8")
        preamble, statement, thm = _split(text)
        if not statement:
            continue
        out.append(Problem(name=f.stem, benchmark=benchmark, preamble=preamble,
                           statement=statement, informal=_informal(text, thm)))
    return out

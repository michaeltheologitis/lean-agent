"""Problems to prove, and how to load them.

A problem is a `.lean` file split into two parts:

  * **preamble** — everything before the target theorem: imports, `open`s, and any
    definitions / helper lemmas. This is run once to pre-warm the Lean environment AND is put
    into the agent's system prompt — so both Lean and the LLM get the concepts.
  * **statement** — the target `theorem <name> ... :=` (the goal; the agent supplies the proof).

The target theorem is the **last** `theorem` in the file (so an experiment file can list
helper definitions/lemmas above the goal). For a plain benchmark file there's just one.

  load(benchmark)        — `smoke` / `minif2f` / `putnam` from `data/<benchmark>/`.
  load_experiment(name)  — `data/experiments/<name>/*.lean`; each file is one *condition*
                           (e.g. `notated.lean` vs `raw.lean`) of the same proposition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .settings import PROJECT_ROOT

DATA = PROJECT_ROOT / "data"
_THM_RE = re.compile(r"^theorem\s+(\w+)", re.MULTILINE)


def _informal(text: str, name: str) -> str:
    """The `/-- ... -/` docstring above the target theorem (PutnamBench has these); else ""."""
    m = re.search(r"/--(.*?)-/\s*\ntheorem " + re.escape(name), text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _split(text: str) -> tuple[str, str, str]:
    """Return (preamble, statement, name). Statement is the target theorem minus its
    `:= sorry` / `:= by sorry`. Preamble is everything above it, doc-comments stripped."""
    matches = list(_THM_RE.finditer(text))
    if not matches:
        return text.strip(), "", ""
    m = matches[-1]
    name = m.group(1)
    # Preamble = the runnable declarations above the goal: drop doc-comments and line comments.
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


@dataclass
class Problem:
    name: str
    benchmark: str
    preamble: str       # imports + given definitions (pre-warms the env AND the system prompt)
    statement: str      # the target `theorem <name> ... :=`  (no sorry)
    informal: str = ""

    def prompt(self) -> str:
        informal = f"Informal statement:\n{self.informal}\n\n" if self.informal else ""
        first = self.statement.splitlines()[0]
        return (
            "Prove this Lean 4 theorem. The imports and any given definitions are ALREADY "
            "loaded in the environment — use them directly, do not repeat them.\n\n"
            f"{informal}Goal:\n```lean\n{self.statement} := sorry\n```\n\n"
            f"Call `lean_check(code)` with the COMPLETE declaration and your proof "
            f"(`{first} ... := <proof>`), read the feedback, and iterate. When it reports the "
            "proof is valid and complete, call `final_answer(\"done\")`."
        )


def _load_dir(directory: Path, benchmark: str, *, names: list[str] | None = None,
              name_prefix: str = "") -> list[Problem]:
    out: list[Problem] = []
    for f in sorted(directory.glob("*.lean")):
        if names and f.stem not in names:
            continue
        text = f.read_text(encoding="utf-8")
        preamble, statement, thm = _split(text)
        if not statement:
            continue
        out.append(Problem(
            name=f"{name_prefix}{f.stem}",
            benchmark=benchmark,
            preamble=preamble,
            statement=statement,
            informal=_informal(text, thm),
        ))
    return out


def load(benchmark: str, *, names: list[str] | None = None) -> list[Problem]:
    """Load `smoke` / `minif2f` / `putnam` problems from `data/<benchmark>/`."""
    if benchmark not in ("smoke", "minif2f", "putnam"):
        raise ValueError(f"unknown benchmark {benchmark!r}")
    return _load_dir(DATA / benchmark, benchmark, names=names)


def load_experiment(name: str, *, names: list[str] | None = None) -> list[Problem]:
    """Load the conditions of an experiment from `data/experiments/<name>/` (one `.lean`
    file per condition, e.g. `notated.lean` and `raw.lean`)."""
    directory = DATA / "experiments" / name
    if not directory.is_dir():
        raise ValueError(f"no experiment at {directory}")
    return _load_dir(directory, "experiment", names=names, name_prefix=f"{name}/")

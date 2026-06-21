"""Benchmarks — load Lean problems to prove.

Every problem is the same thing: a `.lean` file with a `sorry` to fill, compiled in a Lean
project, graded by "compiles AND no sorry/admit". So there's one `Problem`; the three
sources differ only in `load(...)`:

  smoke   — trivial core-Lean goals (no Mathlib); the in-repo runnable check.
  minif2f — easy contest problems (Mathlib v4.24.0); where a weak model gets signal.
  putnam  — hard (Mathlib v4.27.0); a small vendored subset — the full set comes with a
            PutnamBench checkout.

Real grading needs a built Lean project at the matching Mathlib version: clone the source
repo as a gitignored sibling and `lake exe cache get` it (see `data/<name>/SOURCE.md`), or
pass `project=`/`--project`. `smoke` runs against the in-repo `lean_project_core/`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .settings import PROJECT_ROOT
from .tools import compile_file, has_sorry

DATA = PROJECT_ROOT / "data"
PROJECTS = {
    "smoke": PROJECT_ROOT / "lean_project_core",
    "minif2f": PROJECT_ROOT / "miniF2F-lean4",
    "putnam": PROJECT_ROOT / "PutnamBench" / "lean4",
}


def _norm(s: str) -> str:
    return " ".join(s.split())


def _statement(text: str, name: str) -> str:
    """The theorem signature, minus the trailing proof opener — handles `:= sorry`,
    `:= by sorry`, and the multi-line `:=\\nsorry` (Putnam's format)."""
    lines = text.splitlines()
    i = next((k for k, ln in enumerate(lines) if ln.startswith(f"theorem {name}")), None)
    if i is None:
        return ""
    block = "\n".join(lines[i:]).rstrip()
    if block.endswith("sorry"):
        block = block[: -len("sorry")].rstrip()
    if block.endswith("by"):
        block = block[: -len("by")].rstrip()
    if block.endswith(":="):
        block = block[:-2].rstrip()
    return block


def _informal(text: str, name: str) -> str:
    """The `/-- ... -/` docstring above the theorem (PutnamBench has these); else ""."""
    m = re.search(r"/--(.*?)-/\s*\ntheorem " + re.escape(name), text, re.DOTALL)
    return m.group(1).strip() if m else ""


@dataclass
class Problem:
    name: str
    benchmark: str
    project: Path
    stub: str            # the .lean file content, with `sorry` to fill
    informal: str = ""   # informal statement, if known
    statement: str = ""  # theorem signature, for the advisory statement_changed check

    def prepare(self, work_dir) -> Path:
        """Write the editable copy into `work_dir` and return it."""
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        f = work_dir / f"{self.name}.lean"
        f.write_text(self.stub, encoding="utf-8")
        return f

    def prompt(self, work_file: Path) -> str:
        informal = f"Informal statement:\n{self.informal}\n\n" if self.informal else ""
        return (
            f"You are solving a {self.benchmark} problem in Lean 4.\n\n{informal}"
            f"The file `{work_file}` contains (note the `sorry`):\n```lean\n"
            f"{self.stub.rstrip()}\n```\n\n"
            "Replace the `sorry` with a real proof so the file compiles with NO errors and "
            "NO `sorry`/`admit` — keep the theorem statement unchanged, only fill the proof. "
            f"Call `write_and_check(file_path='{work_file}', content=...)` with the COMPLETE "
            "file to compile it, read the output, and iterate. When it compiles cleanly with "
            "no `sorry`, call `final_answer(\"done\")`."
        )

    def grade(self, work_file) -> dict:
        """passed = compiles AND no sorry/admit. `statement_changed` is advisory (never gates
        passed, never shown to the agent): did the original theorem signature survive."""
        text = Path(work_file).read_text(encoding="utf-8")
        changed = bool(self.statement) and _norm(self.statement) not in _norm(text)
        if has_sorry(text):
            return {"passed": False, "reason": "contains sorry/admit", "statement_changed": changed}
        out = compile_file(str(work_file))
        passed = "status: compiled successfully" in out
        reason = "ok" if passed else out.splitlines()[0][:200]
        return {"passed": passed, "reason": reason, "statement_changed": changed}


def load(benchmark: str, *, names: list[str] | None = None, project=None) -> list[Problem]:
    """Load problems for one benchmark as `Problem`s. `names` is an optional allowlist."""
    if benchmark not in PROJECTS:
        raise ValueError(f"unknown benchmark {benchmark!r}; have {sorted(PROJECTS)}")
    project = Path(project) if project else PROJECTS[benchmark]
    out: list[Problem] = []
    for f in sorted((DATA / benchmark).glob("*.lean")):
        if names and f.stem not in names:
            continue
        text = f.read_text(encoding="utf-8")
        out.append(Problem(
            name=f.stem,
            benchmark=benchmark,
            project=project,
            stub=text,
            informal=_informal(text, f.stem),
            statement=_statement(text, f.stem),
        ))
    return out

"""PutnamBench adapter.

Loads the vendored Putnam statements from `data/putnam/*.lean` (extracted from PutnamBench
with ground-truth answers stripped) and produces shared `Problem`s that compile inside
`lean_project/` (Mathlib). Parsing logic descends from Nhan's `putnam_loader.py`.

Two task types (PutnamBench's own split):
  * "proof"        — no answer def; the agent fills the single theorem `sorry`.
  * "answer_proof" — also has `abbrev ..._solution := sorry`; the closed-form answer was
                     stripped, so the agent would have to guess it. Harder + ill-posed for a
                     blind baseline, so `load()` defaults to proof-only.

Heads-up: these statements were extracted against PutnamBench's Lean project (Mathlib
v4.27.0). `lean_project/` here is a different Mathlib pin — verify version compatibility on a
machine with the toolchain before trusting the grades. (Loaders + parsing are unit-tested;
actual Mathlib grading is not runnable on a box without the built project.)
"""

from __future__ import annotations

import re
from pathlib import Path

from ..settings import PROJECT_ROOT
from . import Problem

DATA_DIR = PROJECT_ROOT / "data" / "putnam"
LEAN_PROJECT = PROJECT_ROOT / "lean_project"

_YEAR_RE = re.compile(r"putnam_(\d{4})_([ab]\d+)", re.IGNORECASE)
_SOLUTION_RE = re.compile(r"^(abbrev|def)\s+\S*_solution\b")


def _parse(path: Path) -> dict:
    """Extract {informal, formal_statement, has_answer, year, label} from one stub file."""
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    name = path.stem

    thm_idx = next((i for i, ln in enumerate(lines) if ln.startswith(f"theorem {name}")), None)

    # docstring: the /-- ... -/ block immediately above the theorem, if any
    informal = ""
    doc_start = thm_idx if thm_idx is not None else len(lines)
    if thm_idx is not None and thm_idx >= 1:
        close = None
        for i in range(thm_idx - 1, -1, -1):
            if lines[i].strip().endswith("-/"):
                close = i
                break
            if lines[i].strip():
                break
        if close is not None:
            open_i = next(
                (i for i in range(close, -1, -1) if lines[i].lstrip().startswith("/--")), None
            )
            if open_i is not None:
                block = "\n".join(lines[open_i:close + 1])
                informal = block.replace("/--", "", 1).rsplit("-/", 1)[0].strip()
                doc_start = open_i

    has_answer = any(_SOLUTION_RE.match(ln.strip()) for ln in lines[:doc_start])

    # formal statement = theorem block minus the trailing `:= sorry`
    formal = ""
    if thm_idx is not None:
        block = "\n".join(lines[thm_idx:]).rstrip()
        if block.endswith("sorry"):
            block = block[: -len("sorry")].rstrip()
        if block.endswith(":="):
            block = block[:-2].rstrip()
        formal = block

    ym = _YEAR_RE.search(name)
    return {
        "informal": informal,
        "formal_statement": formal,
        "has_answer": has_answer,
        "year": int(ym.group(1)) if ym else None,
        "label": ym.group(2) if ym else None,
    }


def load(
    *,
    names: list[str] | None = None,
    years: tuple[int, int] | None = None,
    task_type: str | None = "proof",
    data_dir: Path | None = None,
    project: Path | None = None,
) -> list[Problem]:
    """Load Putnam problems as shared `Problem`s.

    names: explicit allowlist of problem stems.
    years: inclusive (min, max) filter.
    task_type: "proof" (default), "answer_proof", or None for both.
    """
    data_dir = Path(data_dir or DATA_DIR)
    project = Path(project or LEAN_PROJECT)

    out: list[Problem] = []
    for f in sorted(data_dir.glob("*.lean")):
        if names and f.stem not in names:
            continue
        meta = _parse(f)
        this_type = "answer_proof" if meta["has_answer"] else "proof"
        if task_type and this_type != task_type:
            continue
        if years and (meta["year"] is None or not (years[0] <= meta["year"] <= years[1])):
            continue
        out.append(Problem(
            name=f.stem,
            benchmark="putnam",
            project=project,
            stub_text=f.read_text(encoding="utf-8"),
            informal=meta["informal"],
            formal_statement=meta["formal_statement"],
        ))
    return out

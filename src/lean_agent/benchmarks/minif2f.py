"""MiniF2F adapter.

Loads the vendored MiniF2F statements from `data/minif2f/*.lean` and produces shared
`Problem`s. MiniF2F is the right benchmark for weak models: it has genuinely easy
algebra/number-theory problems (unlike Putnam), so a small model like gpt-5.4-nano can
actually land some — which is what gives the baseline signal.

Each file is self-contained: `import Mathlib`, `set_option maxHeartbeats 0`, an `open`, and
one `theorem ... := by sorry`. There is no in-file informal statement (MiniF2F has none), so
`informal` is empty.

Source + Mathlib version: see `data/minif2f/SOURCE.md`. The statements were authored against
Mathlib v4.24.0; `lean_project/` here is a different pin — point `--project`/`load(project=)`
at a matching built project before trusting grades.
"""

from __future__ import annotations

from pathlib import Path

from ..settings import PROJECT_ROOT
from . import Problem

DATA_DIR = PROJECT_ROOT / "data" / "minif2f"
# Default grading project: a sibling miniF2F-lean4 checkout (gitignored). Clone it and run
# `lake exe cache get` so the vendored statements compile at their own Mathlib (v4.24.0).
# Override with `--project` / `load(project=)` to point elsewhere.
LEAN_PROJECT = PROJECT_ROOT / "miniF2F-lean4"


def _formal_statement(text: str, name: str) -> str:
    """The theorem signature, minus the trailing `:= by sorry` / `:= sorry`."""
    lines = text.splitlines()
    thm_idx = next((i for i, ln in enumerate(lines) if ln.startswith(f"theorem {name}")), None)
    if thm_idx is None:
        return ""
    block = "\n".join(lines[thm_idx:]).rstrip()
    for tail in (":= by sorry", ":=by sorry", ":= sorry"):
        if block.endswith(tail):
            return block[: -len(tail)].rstrip()
    return block


def load(
    *,
    names: list[str] | None = None,
    data_dir: Path | None = None,
    project: Path | None = None,
) -> list[Problem]:
    """Load MiniF2F problems as shared `Problem`s. `names` is an optional allowlist."""
    data_dir = Path(data_dir or DATA_DIR)
    project = Path(project or LEAN_PROJECT)

    out: list[Problem] = []
    for f in sorted(data_dir.glob("*.lean")):
        if names and f.stem not in names:
            continue
        text = f.read_text(encoding="utf-8")
        out.append(Problem(
            name=f.stem,
            benchmark="minif2f",
            project=project,
            stub_text=text,
            informal="",
            formal_statement=_formal_statement(text, f.stem),
        ))
    return out

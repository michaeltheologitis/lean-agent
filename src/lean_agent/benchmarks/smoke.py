"""Smoke benchmark — trivial, Mathlib-free Lean goals.

Purpose: live-test the whole agent ↔ Lean ↔ logs loop without a multi-GB Mathlib build.
These goals compile in `lean_project_core/` (core Lean only), so any teammate with just a
Lean toolchain installed can confirm the harness works end-to-end. Not a real measure of
proving ability — a plumbing check.
"""

from __future__ import annotations

from pathlib import Path

from ..settings import PROJECT_ROOT
from . import Problem

DATA_DIR = PROJECT_ROOT / "data" / "smoke"
CORE_PROJECT = PROJECT_ROOT / "lean_project_core"


def _formal_statement(text: str, name: str) -> str:
    line = next((ln for ln in text.splitlines() if ln.startswith(f"theorem {name}")), "")
    for tail in (":= by sorry", ":=by sorry", ":= sorry"):
        if line.rstrip().endswith(tail):
            return line.rstrip()[: -len(tail)].rstrip()
    return line.rstrip()


def load(
    *,
    names: list[str] | None = None,
    data_dir: Path | None = None,
    project: Path | None = None,
) -> list[Problem]:
    """Load smoke problems as shared `Problem`s. `names` is an optional allowlist."""
    data_dir = Path(data_dir or DATA_DIR)
    project = Path(project or CORE_PROJECT)

    out: list[Problem] = []
    for f in sorted(data_dir.glob("*.lean")):
        if names and f.stem not in names:
            continue
        text = f.read_text(encoding="utf-8")
        out.append(Problem(
            name=f.stem,
            benchmark="smoke",
            project=project,
            stub_text=text,
            informal="A trivial core-Lean goal (no Mathlib).",
            formal_statement=_formal_statement(text, f.stem),
        ))
    return out

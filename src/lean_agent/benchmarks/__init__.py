"""Benchmarks — decoupled adapters over one shared `Problem` mechanic.

Every benchmark problem is the same thing: a `.lean` file with a `sorry` to fill, compiled
inside a Lean project, graded by "compiles AND no sorry/admit". So there is ONE `Problem`
type here; each benchmark module (`putnam`, `minif2f`, `smoke`) only differs in its
`load()` — where the statements come from and which Lean project they compile against.

No registry / framework: a new benchmark is a new module with a `load()`, picked explicitly
by the runner. The grader is the harness's job and lives here — never an agent tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..lean import has_forbidden, lean_check_compiles

GRADE_TIMEOUT = 180


def _norm(text: str) -> str:
    return " ".join(text.split())


@dataclass
class Grade:
    """The harness verdict. `statement_changed` is advisory only (never gates `passed`,
    never shown to the agent): a heuristic for whether the original theorem signature
    survived, so a run that 'won' by weakening the goal is visible on review."""
    passed: bool
    reason: str
    statement_changed: bool


@dataclass
class Problem:
    name: str
    benchmark: str
    project: Path                 # the Lean project this problem compiles inside
    stub_text: str                # the .lean file content, with `sorry` to fill
    informal: str = ""            # informal statement, if known (may be empty)
    formal_statement: str = ""    # theorem signature, for the advisory statement_changed check
    tags: list[str] = field(default_factory=list)

    def prepare(self, work_dir) -> Path:
        """Write the editable copy into `work_dir` (which must be inside `self.project`)
        and return its path. The canonical stub under `data/` is never touched."""
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        work_file = work_dir / f"{self.name}.lean"
        work_file.write_text(self.stub_text, encoding="utf-8")
        return work_file

    def build_prompt(self, work_file: Path) -> str:
        rel = Path(work_file).resolve().relative_to(Path(self.project).resolve()).as_posix()
        informal = f"Informal statement:\n{self.informal}\n\n" if self.informal else ""
        return (
            f"You are solving a {self.benchmark} problem in Lean 4.\n\n"
            f"{informal}"
            f"The file `{rel}` currently contains (note the `sorry`):\n"
            "```lean\n"
            f"{self.stub_text.rstrip()}\n"
            "```\n\n"
            "Replace the `sorry` with a real proof so the file compiles with NO errors and "
            "NO `sorry`/`admit`. Do NOT change the theorem statement — only fill in the "
            "proof. Call `write_and_check(content)` with the COMPLETE file contents to "
            "compile it, read the Lean output, and iterate. When it compiles cleanly with no "
            "`sorry`, call `final_answer(\"done\")`."
        )

    def grade(self, work_file) -> Grade:
        """passed = compiles AND no sorry/admit. Compile happens in `self.project`."""
        final = Path(work_file).read_text(encoding="utf-8")
        statement_changed = bool(self.formal_statement) and (
            _norm(self.formal_statement) not in _norm(final)
        )
        if has_forbidden(final):
            return Grade(False, "proof still contains sorry/admit", statement_changed)
        rel = Path(work_file).resolve().relative_to(Path(self.project).resolve()).as_posix()
        out = lean_check_compiles.forward(str(self.project), rel, GRADE_TIMEOUT)
        passed = "status: compiled successfully" in out
        reason = "ok" if passed else out.splitlines()[0][:200]
        return Grade(passed, reason, statement_changed)

"""
Load and structure PutnamBench Lean4 problems for benchmarking a proof agent.

Parses each lean4/src/*.lean problem file into a Problem object and joins it
with tag/informal metadata from informal/putnam.json.

Each problem file has this shape:

    import Mathlib
    open ...

    abbrev putnam_XXXX_solution : <type> := sorry      # optional, answer-extraction problems
    -- <ground truth answer>                            # the real answer, commented out

    /-- <informal statement> -/
    theorem putnam_XXXX ... := sorry

Two task types:
  * "proof"        -> no answer def; agent fills the single theorem `sorry`.
  * "answer_proof" -> has answer def(s); ground truth is known, so by default we
                      substitute it and the agent still only proves the theorem.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


_DECL_RE = re.compile(r"^(abbrev|def)\s+(\S+)\s*:\s*(.*?)\s*:=\s*sorry\s*$")
_YEAR_RE = re.compile(r"putnam_(\d{4})_([ab]\d+)", re.IGNORECASE)


@dataclass
class AnswerDef:
    """An answer-extraction definition (abbrev/def ..._solution := sorry)."""
    keyword: str          # "abbrev" or "def"
    name: str             # e.g. putnam_1962_a2_solution
    type: str             # the Lean type after the colon
    ground_truth: str | None  # the commented-out real answer, if present


@dataclass
class Problem:
    name: str                       # putnam_1962_a1
    year: int | None
    label: str | None               # a1, b3, ...
    tags: list[str]
    informal_statement: str
    informal_solution: str
    imports: list[str]
    opens: list[str]
    answer_defs: list[AnswerDef]
    docstring: str                  # the /-- ... -/ text (informal statement in-file)
    formal_statement: str           # the theorem signature, no `:= sorry`
    raw: str = field(repr=False)    # original file text
    path: Path | None = field(default=None, repr=False)

    @property
    def task_type(self) -> str:
        return "answer_proof" if self.answer_defs else "proof"

    @property
    def has_answer(self) -> bool:
        return bool(self.answer_defs)

    def build_file(self, proof: str, fill_answers: bool = True) -> str:
        """
        Assemble a complete, compilable .lean file from a candidate proof.

        proof: the proof term/tactic block that replaces the theorem's `sorry`,
               e.g. "by simp" or a multi-line "by\n  ...".
        fill_answers: substitute known ground-truth answers into answer defs so
               the agent is judged only on the theorem proof. If False, answer
               defs keep `sorry` (use only if your agent also produces answers).
        """
        lines: list[str] = []
        lines.extend(self.imports)
        if self.opens:
            lines.append("")
            lines.extend(self.opens)

        for ad in self.answer_defs:
            lines.append("")
            if fill_answers and ad.ground_truth:
                lines.append(f"{ad.keyword} {ad.name} : {ad.type} := {ad.ground_truth}")
            else:
                lines.append(f"{ad.keyword} {ad.name} : {ad.type} := sorry")

        lines.append("")
        lines.append(self.formal_statement.rstrip())
        # attach the proof; statement already ends right before `:=`
        lines.append(f"  := {proof}" if "\n" not in proof else f"  := {proof}")
        return "\n".join(lines) + "\n"

    def statement_for_agent(self, include_informal: bool = True) -> str:
        """The problem as the agent should see it: statement ending in sorry."""
        parts = []
        if include_informal and self.informal_statement:
            parts.append(f"-- {self.informal_statement}")
        parts.extend(self.imports)
        if self.opens:
            parts.append("")
            parts.extend(self.opens)
        for ad in self.answer_defs:
            parts.append("")
            # show ground-truth-filled answer so the agent proves against it
            if ad.ground_truth:
                parts.append(f"{ad.keyword} {ad.name} : {ad.type} := {ad.ground_truth}")
            else:
                parts.append(f"{ad.keyword} {ad.name} : {ad.type} := sorry")
        parts.append("")
        parts.append(self.formal_statement.rstrip())
        parts.append("  := sorry")
        return "\n".join(parts) + "\n"


def _parse_lean_file(path: Path, meta: dict) -> Problem:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    name = path.stem

    # theorem line (validated to exist for every file)
    thm_idx = next(i for i, l in enumerate(lines) if l.startswith(f"theorem {name}"))

    # docstring: the /-- ... -/ block immediately above the theorem, if any
    doc = ""
    doc_start = thm_idx
    if thm_idx >= 1:
        # walk up to find a closing -/
        close = None
        for i in range(thm_idx - 1, -1, -1):
            if lines[i].strip().endswith("-/"):
                close = i
                break
            if lines[i].strip():  # non-empty, non-comment -> no docstring
                break
        if close is not None:
            open_i = None
            for i in range(close, -1, -1):
                if lines[i].lstrip().startswith("/--"):
                    open_i = i
                    break
            if open_i is not None:
                block = "\n".join(lines[open_i:close + 1])
                doc = block.replace("/--", "", 1).rsplit("-/", 1)[0].strip()
                doc_start = open_i

    header = lines[:doc_start]
    imports = [l for l in header if l.startswith("import ")]
    opens = [l for l in header if l.startswith("open ")]

    # answer defs + their commented ground truth
    answer_defs: list[AnswerDef] = []
    i = 0
    while i < len(header):
        m = _DECL_RE.match(header[i].strip())
        if m:
            gt_lines = []
            j = i + 1
            while j < len(header) and header[j].lstrip().startswith("--"):
                gt_lines.append(header[j].lstrip()[2:].strip())
                j += 1
            gt = " ".join(gt_lines).strip() or None
            answer_defs.append(AnswerDef(m.group(1), m.group(2), m.group(3), gt))
            i = j
        else:
            i += 1

    # formal statement = theorem block minus the trailing proof
    thm_block = "\n".join(lines[thm_idx:]).rstrip()
    if thm_block.endswith("sorry"):
        thm_block = thm_block[: -len("sorry")].rstrip()
    if thm_block.endswith(":="):
        thm_block = thm_block[:-2].rstrip()
    formal_statement = thm_block

    ym = _YEAR_RE.search(name)
    year = int(ym.group(1)) if ym else None
    label = ym.group(2) if ym else None

    return Problem(
        name=name,
        year=year,
        label=label,
        tags=meta.get("tags", []),
        informal_statement=meta.get("informal_statement", ""),
        informal_solution=meta.get("informal_solution", ""),
        imports=imports,
        opens=opens,
        answer_defs=answer_defs,
        docstring=doc,
        formal_statement=formal_statement,
        raw=raw,
        path=path,
    )


def load_problems(
    repo_path: str | Path,
    tags: list[str] | None = None,
    years: tuple[int, int] | None = None,
    task_type: str | None = None,
    names: list[str] | None = None,
) -> list[Problem]:
    """
    Load problems from a cloned PutnamBench repo.

    repo_path: path to the PutnamBench checkout root.
    tags: keep only problems having at least one of these tags.
    years: inclusive (min_year, max_year) filter.
    task_type: "proof" or "answer_proof".
    names: explicit allowlist of problem names.
    """
    repo = Path(repo_path)
    src = repo / "lean4" / "src"
    meta_raw = json.loads((repo / "informal" / "putnam.json").read_text(encoding="utf-8"))
    meta = {e["problem_name"]: e for e in meta_raw}

    out: list[Problem] = []
    for f in sorted(src.glob("*.lean")):
        if f.stem in ("Mathlib",):  # safety, shouldn't occur
            continue
        p = _parse_lean_file(f, meta.get(f.stem, {}))
        if names and p.name not in names:
            continue
        if tags and not (set(tags) & set(p.tags)):
            continue
        if years and (p.year is None or not (years[0] <= p.year <= years[1])):
            continue
        if task_type and p.task_type != task_type:
            continue
        out.append(p)
    return out


def iter_problems(repo_path: str | Path, **kw) -> Iterator[Problem]:
    yield from load_problems(repo_path, **kw)


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    probs = load_problems(repo)
    proof = sum(1 for p in probs if p.task_type == "proof")
    answer = len(probs) - proof
    with_gt = sum(1 for p in probs if p.has_answer and all(a.ground_truth for a in p.answer_defs))
    print(f"loaded {len(probs)} problems")
    print(f"  proof-only      : {proof}")
    print(f"  answer+proof    : {answer}  (ground truth recovered for {with_gt})")
    print(f"  years           : {min(p.year for p in probs if p.year)}–{max(p.year for p in probs if p.year)}")

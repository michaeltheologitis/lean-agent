"""
Verify candidate proofs against PutnamBench problems by compiling them with Lean.

The only trustworthy judge of a Lean proof is the Lean compiler. This module
assembles a complete file from a Problem + candidate proof, runs it through the
project's Lean toolchain + Mathlib, and reports pass/fail.

Requires a *built* lean4/ project: elan installed, and `lake exe cache get`
already run inside the repo's lean4/ directory so Mathlib resolves quickly.

A proof passes only if:
  - the candidate contains no `sorry` / `admit` (anti-cheat),
  - Lean exits 0,
  - the output has no error,
  - the output has no "uses 'sorry'" / sorryAx warning.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .putnam_loader import Problem


_CHEAT_TOKENS = ("sorry", "admit", "sorryAx")


@dataclass
class VerifyResult:
    ok: bool
    status: str          # pass | cheat | compile_error | has_sorry | timeout | error
    problem: str
    proof: str
    output: str          # combined lean stdout+stderr (trimmed)
    file: str | None = None  # assembled source, kept when keep_file=True


def _looks_like_cheat(proof: str) -> bool:
    # crude token scan; word-boundary-ish to avoid matching e.g. "sorryfree"
    import re
    return any(re.search(rf"\b{re.escape(t)}\b", proof) for t in _CHEAT_TOKENS)


def verify_proof(
    problem: Problem,
    proof: str,
    repo_path: str | Path,
    timeout: int = 300,
    fill_answers: bool = True,
    keep_file: bool = False,
) -> VerifyResult:
    lean4_dir = Path(repo_path) / "lean4"
    if not (lean4_dir / "lakefile.lean").exists() and not (lean4_dir / "lakefile.toml").exists():
        return VerifyResult(False, "error", problem.name, proof,
                            f"no lakefile in {lean4_dir}; is the repo built?")

    if _looks_like_cheat(proof):
        return VerifyResult(False, "cheat", problem.name, proof,
                            "candidate proof contains sorry/admit")

    source = problem.build_file(proof, fill_answers=fill_answers)

    # write into the project so imports + toolchain resolve
    work = lean4_dir / "_bench_tmp"
    work.mkdir(exist_ok=True)
    fname = work / f"{problem.name}_{uuid.uuid4().hex[:8]}.lean"
    fname.write_text(source, encoding="utf-8")

    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(fname)],
            cwd=lean4_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout + "\n" + proc.stderr).strip()
        low = out.lower()

        if "uses 'sorry'" in low or "sorryax" in low:
            status, ok = "has_sorry", False
        elif proc.returncode != 0 or "error:" in low:
            status, ok = "compile_error", False
        else:
            status, ok = "pass", True

    except subprocess.TimeoutExpired:
        out, status, ok = f"timeout after {timeout}s", "timeout", False
    except FileNotFoundError:
        out, status, ok = ("`lake` not found on PATH. Install elan and run "
                           "`lake exe cache get` in lean4/ first."), "error", False
    finally:
        kept = source if keep_file else None
        if not keep_file:
            fname.unlink(missing_ok=True)

    return VerifyResult(ok, status, problem.name, proof, out[:4000], file=kept)


if __name__ == "__main__":
    # smoke test of the assembly path without a built Lean env:
    # picks a trivial-looking statement and shows what would be compiled.
    import sys
    from .putnam_loader import load_problems
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    p = load_problems(repo, names=["putnam_1962_a1"])[0]
    print("Would compile:\n")
    print(p.build_file("by sorry".replace("sorry", "/* proof */")))
    print("(run inside a built lean4/ project to actually verify)")

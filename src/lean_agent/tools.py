"""Lean tools — how the agent interacts with Lean.

Checking whether Lean compiles means running the Lean compiler; nothing substitutes for it.
`write_and_check` writes a file and runs `lake env lean` on it, returning the output for the
agent to read and iterate on. The Lean project is found by walking up to `lean-toolchain`
(how real Lean tooling locates a project), so the agent only passes `(file_path, content)`.

The sorry trap: a file with `sorry` still compiles — Lean emits `declaration uses \`sorry\``
as a *warning* (exit 0). So we flag it explicitly instead of reporting a clean success.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from smolagents import tool

# `sorry` / `admit` are "I give up" placeholders — a proof with either is not a proof.
_FORBIDDEN_RE = re.compile(r"(?<![A-Za-z])(sorry|admit)(?![A-Za-z])")


def has_sorry(text: str) -> bool:
    """True if `text` uses `sorry`/`admit` as a token (an incomplete proof)."""
    return bool(_FORBIDDEN_RE.search(text))


def _project_root(path: Path) -> Path:
    for p in (path, *path.parents):
        if (p / "lean-toolchain").exists():
            return p
    raise ValueError(f"no Lean project (no lean-toolchain found above {path})")


def compile_file(file_path: str, timeout: int = 180) -> str:
    """Run `lake env lean` on a Lean file; return a compact status + compiler output.

    Status is one of: compiled successfully / compiled WITH sorry/admit / compile failed /
    timeout / error.
    """
    path = Path(file_path).expanduser().resolve()
    root = _project_root(path)
    rel = path.relative_to(root).as_posix()
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", rel], cwd=root, text=True,
            capture_output=True, timeout=timeout, check=False,
        )
    except FileNotFoundError:
        return "status: error\nlake/lean not found on PATH"
    except subprocess.TimeoutExpired:
        return f"status: timeout\ntimeout_seconds: {timeout}"

    combined = f"{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        status = "compile failed"
    elif re.search(r"uses\s+\W?sorry|sorryAx", combined, re.IGNORECASE):
        status = "compiled WITH sorry/admit (INCOMPLETE — not a real proof)"
    else:
        status = "compiled successfully"
    return (
        f"status: {status}\n"
        f"exit_code: {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )


@tool
def write_and_check(file_path: str, content: str) -> str:
    """Write a Lean file and compile it; return the compiler output.

    Args:
        file_path: the .lean file to write (inside a Lean project).
        content: the COMPLETE Lean source, with the `sorry` replaced by a real proof
            (no `sorry`/`admit`).
    """
    path = Path(file_path).expanduser()
    if path.suffix != ".lean":
        return "error: file_path must be a .lean file"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    result = compile_file(str(path))
    if has_sorry(content) and "WITH sorry" not in result:
        result = "note: your proof still contains `sorry`/`admit` — not complete.\n" + result
    return result

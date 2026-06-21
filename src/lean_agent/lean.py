"""Lean tool surface — how the agent interacts with Lean.

Two tools:

- `lean_check_compiles` — raw compile check (`lake env lean <file>` or `lake build`). Also
  used by the harness as the grader.
- `make_write_and_check(project, work_file)` — the editing-loop tool the agent actually
  drives: write the whole file, compile it, read the output, iterate. (Promoted from the two
  duplicated copies that used to live in the experiment scripts.)

`lean_goal` (proof state) is intentionally NOT here — it lives behind the optional
`lean-lsp-mcp` integration, not the baseline.

The sorry trap: a Lean file containing `sorry` (or `admit`) still *compiles* — it only emits
a warning, exit code 0. An agent that watches for errors will think it's done. So both the
compile tool and `write_and_check` explicitly flag `sorry`/`admit` in their status line.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from smolagents import tool

# `sorry` / `admit` are "I give up" placeholders — a proof containing either is not a proof.
FORBIDDEN = ("sorry", "admit")
_FORBIDDEN_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(FORBIDDEN) + r")(?![A-Za-z])"
)


def has_forbidden(text: str) -> bool:
    """True if `text` uses `sorry` or `admit` as a token (not inside an identifier)."""
    return bool(_FORBIDDEN_RE.search(text))


def _project_root(project_path: str) -> Path:
    root = Path(project_path).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"project_path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"project_path is not a directory: {root}")
    if not (root / "lean-toolchain").exists():
        raise ValueError(f"project_path is not a Lean project root: {root}")
    return root


def _relative_file(root: Path, file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if root not in (path, *path.parents):
        raise ValueError(f"file_path must be inside project_path: {path}")
    if not path.exists():
        raise ValueError(f"file_path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"file_path is not a file: {path}")
    if path.suffix != ".lean":
        raise ValueError(f"file_path is not a Lean file: {path}")
    return path


def _run_compile_command(cmd: list[str], cwd: Path, timeout_seconds: int) -> str:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, text=True, capture_output=True,
            timeout=timeout_seconds, check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        return (
            f"status: timeout\n"
            f"timeout_seconds: {timeout_seconds}\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}"
        )

    combined = f"{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        status = "compile failed"
    elif re.search(r"declaration uses 'sorry'|uses 'sorry'|sorryAx", combined):
        # Compiles, but the proof is incomplete — the trap the team hit.
        status = "compiled WITH sorry/admit (INCOMPLETE — not a real proof)"
    else:
        status = "compiled successfully"
    return (
        f"status: {status}\n"
        f"exit_code: {proc.returncode}\n"
        f"command: {' '.join(cmd)}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )


@tool
def lean_check_compiles(
    project_path: str,
    file_path: str = "",
    timeout_seconds: int = 120,
) -> str:
    """Check whether a Lean project or one Lean file compiles.

    Args:
        project_path: Path to the Lean project root containing `lean-toolchain`.
        file_path: Optional Lean file to check. When empty, run `lake build`.
            Relative paths are interpreted from `project_path`.
        timeout_seconds: Maximum seconds to allow the compile check to run.
    """
    root = _project_root(project_path)
    if file_path.strip():
        path = _relative_file(root, file_path)
        rel = path.relative_to(root).as_posix()
        return _run_compile_command(
            ["lake", "env", "lean", rel], cwd=root, timeout_seconds=timeout_seconds
        )
    return _run_compile_command(
        ["lake", "build"], cwd=root, timeout_seconds=timeout_seconds
    )


def make_write_and_check(project: Path, work_file: Path, timeout_seconds: int = 180):
    """Build the agent's editing-loop tool for one problem file.

    Returns a `write_and_check(content)` tool: it writes the whole Lean file and compile-
    checks it, returning the compiler output. If the written content still contains
    `sorry`/`admit`, the status line says so explicitly (the file would otherwise compile
    with only a warning).
    """
    project = Path(project).resolve()
    work_file = Path(work_file).resolve()
    rel = work_file.relative_to(project).as_posix()

    @tool
    def write_and_check(content: str) -> str:
        """Write the full Lean file and compile it; returns the compiler output.

        Args:
            content: the COMPLETE Lean source for the problem file, with the `sorry`
                replaced by real Lean (no `sorry`/`admit`).
        """
        work_file.write_text(content, encoding="utf-8")
        result = lean_check_compiles.forward(str(project), rel, timeout_seconds)
        if has_forbidden(content) and "WITH sorry" not in result:
            result = (
                "note: your submission still contains `sorry`/`admit` — it is NOT a "
                "complete proof even if it compiles.\n" + result
            )
        return result

    return write_and_check

"""Lean compile-checking smolagents tools."""

from __future__ import annotations

import subprocess
from pathlib import Path

from smolagents import tool


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
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return (
            f"status: timeout\n"
            f"timeout_seconds: {timeout_seconds}\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    status = "compiled successfully" if proc.returncode == 0 else "compile failed"
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
            ["lake", "env", "lean", rel],
            cwd=root,
            timeout_seconds=timeout_seconds,
        )
    return _run_compile_command(
        ["lake", "build"],
        cwd=root,
        timeout_seconds=timeout_seconds,
    )


LEAN_TOOLS = [lean_check_compiles]

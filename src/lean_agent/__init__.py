"""lean-agent — a common, inspectable baseline theorem-proving agent for Lean 4."""

from .settings import Settings, get_settings
from .lean import lean_check_compiles, make_write_and_check, has_forbidden
from .logs import save_run
from .benchmarks import Problem, Grade
from .agent import build_agent, build_model, solve, RunResult

__all__ = [
    "Settings",
    "get_settings",
    "lean_check_compiles",
    "make_write_and_check",
    "has_forbidden",
    "save_run",
    "Problem",
    "Grade",
    "build_agent",
    "build_model",
    "solve",
    "RunResult",
]

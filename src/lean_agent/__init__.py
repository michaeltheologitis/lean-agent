"""lean-agent — a common, inspectable baseline theorem-proving agent for Lean 4.

The core library: an agent that proves against a pre-warmed Lean REPL environment (via
LeanInteract). A problem's preamble (imports + definitions) is loaded into both the
environment and the system prompt, so you can test whether giving the agent well-structured
definitions makes it more effective. The benchmarks/experiments that feed it live in the
top-level `benchmarks/` folder, not here.
"""

from .settings import Settings, get_settings
from .problem import Problem
from .lean import Lean, LeanResult, lean_config, make_lean_check
from .logs import save_run
from .agent import build_model, solve

__all__ = [
    "Settings",
    "get_settings",
    "Problem",
    "Lean",
    "LeanResult",
    "lean_config",
    "make_lean_check",
    "save_run",
    "build_model",
    "solve",
]

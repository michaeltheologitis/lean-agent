"""lean-agent — a common, inspectable baseline theorem-proving agent for Lean 4.

The agent proves against a pre-warmed Lean REPL environment (via LeanInteract): a problem's
preamble (imports + definitions) is loaded into both the environment and the system prompt,
so you can test whether giving the agent well-structured definitions makes it more effective.
"""

from .settings import Settings, get_settings
from .lean import Lean, LeanResult, lean_config, make_lean_check
from .logs import save_run
from .benchmarks import Problem, load, load_experiment
from .agent import build_model, solve

__all__ = [
    "Settings",
    "get_settings",
    "Lean",
    "LeanResult",
    "lean_config",
    "make_lean_check",
    "save_run",
    "Problem",
    "load",
    "load_experiment",
    "build_model",
    "solve",
]

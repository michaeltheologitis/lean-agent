"""The shared theorem-proving agent.

`solve(problem, lean)` pre-warms BOTH the Lean environment (run the problem's preamble to get a
base env with its definitions) AND the system prompt (append the same preamble), then runs a
smolagents `CodeAgent` whose one tool, `lean_check`, compiles code against that env. The run is
graded by whether any submission was a complete valid proof of the target, then logged.
"""

from __future__ import annotations

from smolagents import OpenAIServerModel, ToolCallingAgent

from .benchmarks import Problem
from .lean import Lean, make_lean_check
from .logs import save_run
from .settings import get_settings

# A ToolCallingAgent (not CodeAgent): the model's job is to call `lean_check` with a blob of
# Lean source. A CodeAgent makes it write Python, and it kept emitting bare Lean that the
# Python parser rejected — derailing the run. Native tool calls pass the Lean as a string arg.
INSTRUCTIONS = (
    "You solve Lean 4 theorem-proving tasks. You are given a target theorem; replace its "
    "`sorry` with a real proof so it compiles with no errors and no `sorry`/`admit`. Call the "
    "`lean_check` tool with your candidate `theorem ... := <proof>` (as the `code` argument) "
    "to compile it against the pre-loaded environment; read the feedback (errors, or the "
    "remaining goal if incomplete) and iterate. The imports and any given definitions are "
    "ALREADY loaded — use them, don't repeat them, and don't restate the theorem differently. "
    "When `lean_check` reports the proof is valid and complete, call `final_answer`."
)


def build_model(**kwargs):
    """Build the configured model (OpenAI `gpt-5.4-nano` by default). `kwargs` pass through
    to `OpenAIServerModel` — e.g. `max_tokens=` for a provider that needs a cap."""
    s = get_settings()
    if not s.api_key:
        raise SystemExit("No API key. Set OPENAI_API_KEY in .env (or a provider override).")
    kwargs.setdefault("client_kwargs", {"timeout": 180, "max_retries": 0})
    return OpenAIServerModel(model_id=s.model_id, api_base=s.api_base, api_key=s.api_key, **kwargs)


def solve(problem: Problem, *, lean: Lean, model=None, max_steps: int = 6, save: bool = True) -> dict:
    """Run the agent on one problem against `lean` (a shared REPL session). Returns a result
    dict (passed / steps / usage / run_dir)."""
    base_env = lean.base_env(problem.preamble)
    record = {"passed": False}
    lean_check = make_lean_check(lean, base_env, problem.statement, record)

    instructions = INSTRUCTIONS
    if problem.preamble.strip():
        instructions += (
            "\n\nAlready loaded in the Lean environment — use these directly (do NOT redeclare "
            f"them):\n```lean\n{problem.preamble.strip()}\n```"
        )
    agent = ToolCallingAgent([lean_check], model=model or build_model(),
                             max_steps=max_steps, instructions=instructions)

    error = None
    answer = ""
    try:
        answer = agent.run(problem.prompt())
    except Exception as exc:  # record API/agent failures, keep the batch going
        error = f"{type(exc).__name__}: {exc}"

    usage = agent.monitor.get_total_token_counts()
    result = {
        "problem": problem.name,
        "benchmark": problem.benchmark,
        "passed": record["passed"],
        "steps": len(agent.memory.steps),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "error": error,
    }
    if save:
        try:
            rd = save_run(agent, answer, run_id=f"{problem.benchmark}-{problem.name}".replace("/", "-"),
                          manifest={k: result[k] for k in ("benchmark", "problem", "passed")})
            result["run_dir"] = str(rd)
        except Exception as exc:
            result["error"] = (error + " | " if error else "") + f"save_run failed: {exc}"
    return result

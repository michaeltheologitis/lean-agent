"""The shared theorem-proving agent.

`solve(problem, lean)` pre-warms BOTH the Lean environment (run the problem's preamble to get a
base env with its definitions) AND the system prompt (append the same preamble), then runs a
smolagents `ToolCallingAgent` whose one tool, `lean_check`, compiles code against that env. The
run is graded by whether any submission was a complete valid proof of the target, then logged.
"""

from __future__ import annotations

from smolagents import OpenAIServerModel, ToolCallingAgent

from .lean import Lean, make_lean_check
from .logs import save_run
from .problem import Problem
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
    """Build the configured model (OpenAI `gpt-5.4-mini` by default). `kwargs` pass through
    to `OpenAIServerModel` — e.g. `max_tokens=` for a provider that needs a cap."""
    s = get_settings()
    if not s.api_key:
        raise SystemExit("No API key. Set OPENAI_API_KEY in .env (or a provider override).")
    kwargs.setdefault("client_kwargs", {"timeout": 180, "max_retries": 0})
    return OpenAIServerModel(model_id=s.model_id, api_base=s.api_base, api_key=s.api_key, **kwargs)


def _prompt(problem: Problem) -> str:
    informal = f"Informal statement:\n{problem.informal}\n\n" if problem.informal else ""
    first = problem.statement.splitlines()[0]
    return (
        "Prove this Lean 4 theorem. The imports and any given definitions are ALREADY loaded "
        "in the environment — use them directly, do not repeat them.\n\n"
        f"{informal}Goal:\n```lean\n{problem.statement} := sorry\n```\n\n"
        f"Call `lean_check(code)` with the COMPLETE declaration and your proof "
        f"(`{first} ... := <proof>`), read the feedback, and iterate. When it reports the "
        "proof is valid and complete, call `final_answer(\"done\")`."
    )


def _system_prompt(problem: Problem, extra_instructions: str = "") -> str:
    prompt = INSTRUCTIONS
    if problem.preamble.strip():
        prompt += (
            "\n\nAlready loaded in the Lean environment — use these directly (do NOT redeclare "
            f"them):\n```lean\n{problem.preamble.strip()}\n```"
        )
    if extra_instructions.strip():
        prompt += f"\n\n{extra_instructions.strip()}"
    return prompt


def solve(problem: Problem, *, lean: Lean, model=None, max_steps: int = 6, save: bool = True,
          extra_instructions: str = "") -> dict:
    """Run the agent on one problem against `lean` (a shared REPL session). Returns a result
    dict (passed / proof / steps / usage / run_dir). `extra_instructions`, if given, is appended
    to the system prompt (e.g. "You do NOT have Mathlib — only core Lean is available")."""
    base_env = lean.base_env(problem.preamble)
    record = {"passed": False}
    lean_check = make_lean_check(lean, base_env, problem.statement, record)
    agent = ToolCallingAgent([lean_check], model=model or build_model(),
                             max_steps=max_steps,
                             instructions=_system_prompt(problem, extra_instructions),
                             verbosity_level=0)  # quiet — the runner/caller prints its own summary

    error = None
    answer = ""
    try:
        answer = agent.run(_prompt(problem))
    except Exception as exc:  # record API/agent failures, keep the batch going
        error = f"{type(exc).__name__}: {exc}"

    usage = agent.monitor.get_total_token_counts()
    result = {
        "problem": problem.name,
        "benchmark": problem.benchmark,
        "passed": record["passed"],
        "proof": record.get("proof"),
        "steps": len(agent.memory.steps),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "error": error,
    }
    if save:
        try:
            manifest = {k: result[k] for k in ("benchmark", "problem", "passed")}
            if extra_instructions.strip():
                manifest["extra_instructions"] = extra_instructions.strip()
            proof = record.get("proof")  # the winning declaration; prepend the preamble so it stands alone
            if proof and problem.preamble.strip():
                proof = f"{problem.preamble.strip()}\n\n{proof}"
            rd = save_run(agent, answer, manifest=manifest, proof=proof,
                          run_id=f"{problem.benchmark}-{problem.name}".replace("/", "-"))
            result["run_dir"] = str(rd)
        except Exception as exc:
            result["error"] = (error + " | " if error else "") + f"save_run failed: {exc}"
    return result

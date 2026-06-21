"""The shared theorem-proving agent.

Everyone runs the same thing: a smolagents `CodeAgent` with the Lean tools and one set of
instructions. `solve(problem)` runs it on one benchmark problem, grades the result, saves the
logs, and returns a plain dict. Parameterize it (`model`, `max_steps`) — don't fork it.
"""

from __future__ import annotations

from smolagents import CodeAgent, OpenAIServerModel

from .benchmarks import Problem
from .logs import save_run
from .settings import get_settings
from .tools import write_and_check

INSTRUCTIONS = (
    "You solve Lean 4 theorem-proving tasks. You get a Lean file with one `sorry`; replace it "
    "with a real proof so the file compiles with no errors and no `sorry`/`admit`. Use "
    "`write_and_check(file_path, content)` to write the COMPLETE file and compile it, then "
    "read the compiler output and iterate. Keep the imports, any `open`, and the exact "
    "theorem statement; only fill in the proof. When it compiles cleanly, call "
    "`final_answer(\"done\")`."
)


def build_model(**kwargs):
    """Build the configured model (OpenAI `gpt-5.4-nano` by default). `kwargs` pass through
    to `OpenAIServerModel` — e.g. `max_tokens=` for a provider that needs a cap."""
    s = get_settings()
    if not s.api_key:
        raise SystemExit("No API key. Set OPENAI_API_KEY in .env (or a provider override).")
    kwargs.setdefault("client_kwargs", {"timeout": 180, "max_retries": 0})
    return OpenAIServerModel(model_id=s.model_id, api_base=s.api_base, api_key=s.api_key, **kwargs)


def solve(problem: Problem, *, work_dir, model=None, max_steps: int = 6, save: bool = True) -> dict:
    """Run the agent on one problem; grade, log, and return a result dict.

    `work_dir` is where the editable copy of the problem file lives (inside its Lean project).
    """
    work_file = problem.prepare(work_dir)
    agent = CodeAgent(
        tools=[write_and_check],
        model=model or build_model(),
        max_steps=max_steps,
        instructions=INSTRUCTIONS,
    )

    error = None
    answer = ""
    try:
        answer = agent.run(problem.prompt(work_file))
    except Exception as exc:  # record API/agent failures, keep the batch going
        error = f"{type(exc).__name__}: {exc}"

    result = problem.grade(work_file)
    usage = agent.monitor.get_total_token_counts()
    if save:
        try:
            rd = save_run(agent, answer, run_id=f"{problem.benchmark}-{problem.name}",
                          manifest={"benchmark": problem.benchmark, "problem": problem.name,
                                    **result})
            result["run_dir"] = str(rd)
        except Exception as exc:
            error = (error + " | " if error else "") + f"save_run failed: {exc}"

    result.update(problem=problem.name, benchmark=problem.benchmark,
                  steps=len(agent.memory.steps), input_tokens=usage.input_tokens,
                  output_tokens=usage.output_tokens, error=error)
    return result

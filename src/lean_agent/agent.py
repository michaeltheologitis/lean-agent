"""The single shared theorem-proving agent.

Everyone runs the same agent. `build_agent` wires a model + the Lean tools + the system
instructions; `solve` runs it on one benchmark problem and returns a structured result
(passed / usage / paths) after grading and logging. Don't fork this per experiment —
parameterize it (`model`, `max_steps`, `extra_tools`).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from smolagents import CodeAgent, OpenAIServerModel

from .benchmarks import Problem
from .lean import make_write_and_check
from .logs import save_run
from .settings import get_settings

INSTRUCTIONS = (
    "You solve Lean 4 theorem-proving tasks. You are given a Lean file containing exactly "
    "one `sorry`. Replace the `sorry` with a real proof so the file compiles with no errors "
    "and no `sorry`/`admit`. Use the `write_and_check` tool to write the COMPLETE file and "
    "compile it, then read the compiler output and iterate. Keep the imports, any `open`, and "
    "the exact theorem statement unchanged — only fill in the proof. When it compiles cleanly "
    "with no `sorry`, call `final_answer(\"done\")`."
)


def build_model(*, max_tokens: int | None = None, timeout: int = 180, **model_kwargs: Any):
    """Build the configured OpenAI-compatible model. Defaults come from `get_settings()`
    (OpenAI `gpt-5.4-nano`). `model_kwargs` pass through to `OpenAIServerModel`.

    `max_tokens` is left unset by default — gpt-5 reasoning models use
    `max_completion_tokens`, and the old explicit cap existed only to dodge a Nebius
    gateway timeout. Pass it (or other kwargs) for non-OpenAI providers that need a cap.
    """
    s = get_settings()
    if not s.api_key:
        raise SystemExit(
            "No model API key. Set OPENAI_API_KEY in .env (or a provider override)."
        )
    if max_tokens is not None:
        model_kwargs.setdefault("max_tokens", max_tokens)
    model_kwargs.setdefault("client_kwargs", {"timeout": timeout, "max_retries": 0})
    return OpenAIServerModel(
        model_id=s.model_id, api_base=s.api_base, api_key=s.api_key, **model_kwargs
    )


def build_agent(
    tools: Sequence[Any],
    *,
    model: Any = None,
    max_steps: int = 6,
    instructions: str = INSTRUCTIONS,
) -> CodeAgent:
    """Construct the shared CodeAgent with a given tool list."""
    return CodeAgent(
        tools=list(tools),
        model=model if model is not None else build_model(),
        max_steps=max_steps,
        instructions=instructions,
    )


@dataclass
class RunResult:
    """One problem attempt — what the runner records and prints."""
    benchmark: str
    problem: str
    passed: bool
    reason: str
    statement_changed: bool
    steps: int
    input_tokens: int
    output_tokens: int
    run_dir: str | None = None
    error: str | None = None
    work_file: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def solve(
    problem: Problem,
    *,
    work_dir,
    model: Any = None,
    max_steps: int = 6,
    extra_tools: Sequence[Any] = (),
    save: bool = True,
) -> RunResult:
    """Run the agent on one problem, grade it, save logs, return a `RunResult`.

    `work_dir` is where the editable copy of the problem file lives (inside its Lean
    project). The agent never touches the canonical stub under `data/`.
    """
    model = model if model is not None else build_model()
    work_file = problem.prepare(work_dir)
    write_and_check = make_write_and_check(problem.project, work_file)
    agent = build_agent([write_and_check, *extra_tools], model=model, max_steps=max_steps)

    error: str | None = None
    answer: Any = ""
    try:
        answer = agent.run(problem.build_prompt(work_file))
    except Exception as exc:  # record API/agent failures, keep the batch going
        error = f"{type(exc).__name__}: {exc}"

    grade = problem.grade(work_file)
    usage = agent.monitor.get_total_token_counts()
    steps = len([s for s in agent.memory.steps if getattr(s, "token_usage", None)])

    run_dir = None
    if save:
        try:
            rd = save_run(
                agent, answer,
                run_id=f"{problem.benchmark}-{problem.name}",
                extra_manifest={
                    "benchmark": problem.benchmark,
                    "problem": problem.name,
                    "passed": grade.passed,
                    "reason": grade.reason,
                    "statement_changed": grade.statement_changed,
                },
            )
            run_dir = str(rd)
        except Exception as exc:
            error = (error + " | " if error else "") + f"save_run failed: {exc}"

    return RunResult(
        benchmark=problem.benchmark,
        problem=problem.name,
        passed=grade.passed,
        reason=grade.reason if not error else f"{grade.reason} (agent error: {error})",
        statement_changed=grade.statement_changed,
        steps=steps,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        run_dir=run_dir,
        error=error,
        work_file=str(work_file),
    )

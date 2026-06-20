"""Run our tool-using CodeAgent against PutnamBench problems — file-based.

The agent works directly on a local `.lean` file (a `sorry`-stub from
`putnam_problems/`, copied into PutnamBench's built Lean project at Mathlib
v4.27.0 so it compiles). It edits the WHOLE file via `write_and_check` and may
also call `lean_goal` for the proof-state, iterating on Lean's errors.

The agent is free to do whatever it wants. The prompt asks it not to change the
theorem statement, but we do NOT enforce that mid-run or tell it if it does — we
just let it go. Grading is simply: does the file compile, with no `sorry`/`admit`?
We separately RECORD an advisory `statement_changed` flag (for our own review,
never shown to the agent) so a run that "won" by weakening the goal is visible.

  * local files = `putnam_problems/` (run extract_problems.py to regenerate).
  * extractor   = PutnamBench's loader (enumeration + the original statement).
  * grading     = compiles AND no sorry/admit. `statement_changed` is advisory.

Run:  uv run --with mcp --with mcpadapt python experiments/run_putnam.py [N | name ...]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from smolagents import CodeAgent, OpenAIServerModel, tool

from lean_agent.lean_tools import lean_check_compiles
from lean_agent.putnambench.putnam_loader import Problem, load_problems
from lean_agent.settings import get_settings, save_run

ROOT = Path(__file__).resolve().parents[1]
PROBLEMS_DIR = ROOT / "putnam_problems"                 # local sorry-stub files
REPO = str((ROOT / "PutnamBench").resolve())            # for the loader (extractor)
PROJECT = (ROOT / "PutnamBench" / "lean4").resolve()    # built Lean project (Mathlib v4.27.0)
WORK_DIR = PROJECT / "_work"                            # agent's editable copies, inside the project
RESULTS = ROOT / "experiments" / "putnam_results.jsonl"
FORBIDDEN = ("sorry", "admit")                          # a "proof" with these is not a proof
MAX_STEPS = int(os.getenv("PUTNAM_MAX_STEPS", "5"))
TIMEOUT = int(os.getenv("PUTNAM_TIMEOUT", "180"))


def build_model() -> OpenAIServerModel:
    s = get_settings()
    if not s.api_key:
        raise SystemExit("No model API key (NEBIUS_API_KEY) in lean-agent/.env.")
    return OpenAIServerModel(
        model_id=s.model_id,
        api_base=s.api_base,
        api_key=s.api_key,
        max_tokens=4096,
        client_kwargs={"timeout": 180, "max_retries": 0},
    )


def _norm(s: str) -> str:
    return " ".join(s.split())


def has_forbidden(text: str) -> bool:
    return any(re.search(rf"(?<![A-Za-z]){t}(?![A-Za-z])", text) for t in FORBIDDEN)


def grade(problem: Problem, work_file: Path) -> tuple[bool, str, bool]:
    """Returns (passed, detail, statement_changed).

    passed = compiles AND no sorry/admit. `statement_changed` is ADVISORY only
    (for our review): a heuristic 'did the original statement survive in the file'.
    It does NOT affect passed and is never shown to the agent — false positives
    (e.g. `Finset.Icc` rewritten to `Icc`) are fine; a human eyeballs it."""
    final = work_file.read_text(encoding="utf-8")
    statement_changed = _norm(problem.formal_statement) not in _norm(final)
    if has_forbidden(final):
        return False, "proof still contains sorry/admit", statement_changed
    out = lean_check_compiles.forward(
        str(PROJECT), work_file.relative_to(PROJECT).as_posix(), TIMEOUT
    )
    passed = "status: compiled successfully" in out
    return passed, (out if not passed else "ok"), statement_changed


def build_prompt(rel: str, file_text: str, abs_path: str) -> str:
    return (
        "You are solving a PutnamBench problem in Lean 4 (Mathlib).\n\n"
        f"The file `{rel}` currently contains (note the `sorry`):\n"
        "```lean\n"
        f"{file_text}"
        "```\n\n"
        "Your job: replace the `sorry` with real Lean so the file compiles with NO "
        "errors and NO `sorry`/`admit`. Do NOT change the `theorem` statement — only "
        "fill in the proof.\n\n"
        "Use `write_and_check(content)` to write the COMPLETE file contents and "
        "compile it; read the Lean errors and iterate. Keep the imports, any `open`, "
        "and the exact theorem statement.\n\n"
        "You also have `lean_goal(file_path, line)`: after a `write_and_check` that "
        "still ends in `sorry`, call "
        f"`lean_goal('{abs_path}', <line of the sorry>)` to read the proof-state "
        "(hypotheses ⊢ target) and choose your next tactics.\n\n"
        "When the file compiles cleanly with no `sorry`, call `final_answer(\"done\")`."
    )


def make_check_tool(work_file: Path):
    rel = work_file.relative_to(PROJECT).as_posix()

    @tool
    def write_and_check(content: str) -> str:
        """Write the full Lean file and compile it; returns the compiler output.

        Args:
            content: the COMPLETE Lean source for the problem file, with the
                `sorry` replaced by real Lean (no `sorry`/`admit`).
        """
        work_file.write_text(content, encoding="utf-8")
        return lean_check_compiles.forward(str(PROJECT), rel, TIMEOUT)

    return write_and_check


def run_one(problem: Problem, model, extra_tools=()) -> dict:
    src = PROBLEMS_DIR / f"{problem.name}.lean"
    if not src.exists():
        return {"problem": problem.name, "passed": False,
                "reason": "no stub file; run extract_problems.py first"}
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    work_file = WORK_DIR / f"{problem.name}.lean"
    shutil.copy(src, work_file)

    agent = CodeAgent(tools=[make_check_tool(work_file), *extra_tools],
                      model=model, max_steps=MAX_STEPS)
    answer = agent.run(build_prompt(work_file.relative_to(PROJECT).as_posix(),
                                    src.read_text(encoding="utf-8"),
                                    str(work_file)))
    try:
        save_run(agent, answer, run_id=f"putnam-{problem.name}")
    except Exception as exc:
        print(f"[warn] save_run failed for {problem.name}: {exc}")

    passed, detail, statement_changed = grade(problem, work_file)
    usage = agent.monitor.get_total_token_counts()
    return {
        "problem": problem.name,
        "passed": passed,
        "statement_changed": statement_changed,   # advisory; not a pass/fail gate
        "reason": "ok" if passed else detail.splitlines()[0][:200],
        "steps": len([s for s in agent.memory.steps if getattr(s, "token_usage", None)]),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "work_file": str(work_file),
    }


def pick(argv: list[str], by_name: dict[str, Problem]) -> list[Problem]:
    names = sorted(by_name)
    if len(argv) == 1 and argv[0].isdigit():
        chosen = names[: int(argv[0])]
    elif argv:
        chosen = argv
    else:
        chosen = names[:3]
    return [by_name[n] for n in chosen if n in by_name]


def run_batch(problems, model, extra_tools=()) -> int:
    n_pass = 0
    with RESULTS.open("a", encoding="utf-8") as log:
        for i, problem in enumerate(problems, 1):
            rec = run_one(problem, model, extra_tools=extra_tools)
            rec["timestamp"] = datetime.now(timezone.utc).isoformat()
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log.flush()
            n_pass += int(rec["passed"])
            flag = "  [statement_changed]" if rec.get("statement_changed") else ""
            mark = "PASS" if rec["passed"] else f"FAIL ({rec.get('reason','')})"
            print(f"[{i}/{len(problems)}] {problem.name:28s} {mark}{flag}")
    return n_pass


def main() -> None:
    by_name = {p.name: p for p in load_problems(REPO)}    # the extractor
    problems = pick(sys.argv[1:], by_name)
    model = build_model()
    print(f"project: {PROJECT}")
    print(f"problems: {[p.name for p in problems]}  (max_steps={MAX_STEPS})\n")

    # lean_goal (proof-state) from lean-lsp-mcp, like the base branch's sighted
    # agent. Needs `uv run --with mcp --with mcpadapt`.
    from mcp import StdioServerParameters
    from smolagents import ToolCollection

    server = StdioServerParameters(command="uvx", args=["lean-lsp-mcp"], env={**os.environ})
    print("starting lean-lsp-mcp (first lean_goal call boots `lake serve`) ...")
    with ToolCollection.from_mcp(server, trust_remote_code=True,
                                 structured_output=False) as tc:
        goal = next((t for t in tc.tools if t.name == "lean_goal"), None)
        if goal is None:
            raise SystemExit("lean_goal not found in lean-lsp-mcp tools")
        n_pass = run_batch(problems, model, extra_tools=[goal])

    print(f"\n{n_pass}/{len(problems)} passed  ->  {RESULTS}")


if __name__ == "__main__":
    main()

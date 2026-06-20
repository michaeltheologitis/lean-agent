"""Run our tool-using CodeAgent against PutnamBench problems — file-based.

The agent works directly on a local `.lean` file: a problem whose proof (and, for
answer problems, whose `..._solution`) is `sorry`. The file is placed inside
PutnamBench's built Lean project (Mathlib v4.27.0) so it actually compiles. The
agent edits the file via `write_and_check` and compiles it with our own
`lean_check_compiles` tool, iterating on the errors until the file compiles with
NO `sorry`. That same file is the grade.

  * local files  = `putnam_problems/` (sorry-stubs; run extract_problems.py first).
  * extractor    = PutnamBench's loader, used for enumeration + the exact
                   `formal_statement` (anti-tamper) and `ground_truth` (future use).
  * the agent    = edits a copy of one file inside `PutnamBench/lean4/_work/`.

Run:  uv run python experiments/run_putnam.py [N | name ...]
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
FORBIDDEN = ("sorry", "admit")                          # a "proof" containing these is not a proof
MAX_STEPS = int(os.getenv("PUTNAM_MAX_STEPS", "8"))
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


def grade(problem: Problem, work_file: Path) -> tuple[bool, str]:
    """Pass iff: statement unchanged, no sorry/admit left, and it compiles clean.

    The immutable statement comes from the loader's `formal_statement`, so the
    agent can't 'prove' the problem by weakening the theorem."""
    final = work_file.read_text(encoding="utf-8")
    if _norm(problem.formal_statement) not in _norm(final):
        return False, "theorem statement was altered"
    if has_forbidden(final):
        return False, "proof still contains sorry/admit"
    out = lean_check_compiles.forward(
        str(PROJECT), work_file.relative_to(PROJECT).as_posix(), TIMEOUT
    )
    return ("status: compiled successfully" in out), out


def build_prompt(rel: str, file_text: str) -> str:
    return (
        "You are solving a PutnamBench problem in Lean 4 (Mathlib).\n\n"
        f"The file `{rel}` currently contains (note the `sorry`(s)):\n"
        "```lean\n"
        f"{file_text}"
        "```\n\n"
        "Your job: replace every `sorry` with real Lean so the file compiles with "
        "NO errors and NO `sorry`/`admit`. If there is a `..._solution := sorry`, you "
        "must also fill in the correct value — you are NOT given the answer. Do NOT "
        "change the `theorem` statement itself.\n\n"
        "Use `write_and_check(content)` to write the COMPLETE file contents and "
        "compile it; read the Lean errors and iterate. Keep the imports, any `open`, "
        "the solution definition, and the exact theorem statement. When the file "
        "compiles cleanly with no `sorry`, call `final_answer(\"done\")`."
    )


def make_check_tool(work_file: Path):
    rel = work_file.relative_to(PROJECT).as_posix()

    @tool
    def write_and_check(content: str) -> str:
        """Write the full Lean file and compile it; returns the compiler output.

        Args:
            content: the COMPLETE Lean source for the problem file, with each
                `sorry` replaced by real Lean (no `sorry`/`admit`).
        """
        work_file.write_text(content, encoding="utf-8")
        return lean_check_compiles.forward(str(PROJECT), rel, TIMEOUT)

    return write_and_check


def run_one(problem: Problem, model) -> dict:
    src = PROBLEMS_DIR / f"{problem.name}.lean"
    if not src.exists():
        return {"problem": problem.name, "passed": False,
                "reason": "no stub file; run extract_problems.py first"}
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    work_file = WORK_DIR / f"{problem.name}.lean"
    shutil.copy(src, work_file)

    agent = CodeAgent(tools=[make_check_tool(work_file)], model=model, max_steps=MAX_STEPS)
    answer = agent.run(build_prompt(work_file.relative_to(PROJECT).as_posix(),
                                    src.read_text(encoding="utf-8")))
    try:
        save_run(agent, answer, run_id=f"putnam-{problem.name}")
    except Exception as exc:
        print(f"[warn] save_run failed for {problem.name}: {exc}")

    passed, detail = grade(problem, work_file)
    usage = agent.monitor.get_total_token_counts()
    return {
        "problem": problem.name,
        "passed": passed,
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


def main() -> None:
    by_name = {p.name: p for p in load_problems(REPO)}    # the extractor
    problems = pick(sys.argv[1:], by_name)
    model = build_model()
    print(f"project: {PROJECT}")
    print(f"problems: {[p.name for p in problems]}  (max_steps={MAX_STEPS})\n")

    n_pass = 0
    with RESULTS.open("a", encoding="utf-8") as log:
        for i, problem in enumerate(problems, 1):
            rec = run_one(problem, model)
            rec["timestamp"] = datetime.now(timezone.utc).isoformat()
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log.flush()
            n_pass += int(rec["passed"])
            mark = "PASS" if rec["passed"] else f"FAIL ({rec.get('reason','')})"
            print(f"[{i}/{len(problems)}] {problem.name:28s} {mark}")

    print(f"\n{n_pass}/{len(problems)} passed  ->  {RESULTS}")


if __name__ == "__main__":
    main()

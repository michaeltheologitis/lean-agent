"""Run the baseline agent over a benchmark subset, logging every run.

    uv run python scripts/run.py --benchmark smoke   --n 3
    uv run python scripts/run.py --benchmark minif2f  --n 5 --max-steps 6
    uv run python scripts/run.py --benchmark putnam   --names putnam_1962_a1 putnam_1962_a5

Each problem is solved by the shared agent (`lean_agent.solve`), graded (compiles AND no
sorry/admit), and its full logs are written to `logs/<run-folder>/`. A one-line-per-problem
JSONL summary is appended to `results/<benchmark>-<timestamp>.jsonl`. Read `clean_log.md` in
each run folder to see what the model actually did.

Benchmarks: `smoke` (core Lean, no Mathlib — the live plumbing check), `putnam`, `minif2f`.
`putnam`/`minif2f` need a built Lean project at the matching Mathlib version (see each
benchmark's `data/<name>/SOURCE.md`); pass `--project` to point at yours.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lean_agent.agent import build_model, solve
from lean_agent.benchmarks import minif2f, putnam, smoke
from lean_agent.settings import PROJECT_ROOT

LOADERS = {"smoke": smoke.load, "putnam": putnam.load, "minif2f": minif2f.load}
RESULTS_DIR = PROJECT_ROOT / "results"


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--benchmark", choices=sorted(LOADERS), default="smoke")
    p.add_argument("--n", type=int, default=None, help="run the first N problems")
    p.add_argument("--names", nargs="*", default=None, help="explicit problem names")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--project", default=None, help="override the Lean project to compile in")
    p.add_argument("--task-type", default="proof",
                   help="putnam only: proof | answer_proof | all (default proof)")
    p.add_argument("--no-save", action="store_true", help="don't write per-run logs")
    return p.parse_args(argv)


def load_problems(args) -> list:
    kw = {}
    if args.names:
        kw["names"] = args.names
    if args.project:
        kw["project"] = Path(args.project)
    if args.benchmark == "putnam":
        kw["task_type"] = None if args.task_type == "all" else args.task_type
    problems = LOADERS[args.benchmark](**kw)
    if args.n is not None and not args.names:
        problems = problems[: args.n]
    return problems


def main(argv=None) -> int:
    args = parse_args(argv)
    problems = load_problems(args)
    if not problems:
        print(f"no problems matched for benchmark={args.benchmark}", file=sys.stderr)
        return 1

    project = problems[0].project
    work_dir = Path(project) / "_work"
    model = build_model()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / f"{args.benchmark}-{stamp}.jsonl"

    print(f"benchmark={args.benchmark}  project={project}  "
          f"problems={len(problems)}  max_steps={args.max_steps}\n")

    n_pass = 0
    with results_path.open("w", encoding="utf-8") as log:
        for i, problem in enumerate(problems, 1):
            result = solve(problem, work_dir=work_dir, model=model,
                           max_steps=args.max_steps, save=not args.no_save)
            log.write(json.dumps(dataclasses.asdict(result), ensure_ascii=False) + "\n")
            log.flush()
            n_pass += int(result.passed)
            flag = "  [statement_changed]" if result.statement_changed else ""
            mark = "PASS" if result.passed else f"FAIL ({result.reason})"
            print(f"[{i}/{len(problems)}] {problem.name:32s} {mark[:90]}{flag}")

    print(f"\n{n_pass}/{len(problems)} passed  ->  {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

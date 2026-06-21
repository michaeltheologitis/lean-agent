"""Run the baseline agent over a benchmark subset, logging every run.

    uv run python run.py --benchmark smoke   --n 3
    uv run python run.py --benchmark minif2f --n 5 --max-steps 6
    uv run python run.py --benchmark putnam  --names putnam_1962_a1 putnam_1962_a3

Each problem is solved by the shared agent (`lean_agent.solve`), graded (compiles AND no
sorry/admit), and logged to `logs/<run-folder>/` (read `run.md`). A one-line-per-problem
summary is written to `results/<benchmark>-<timestamp>.jsonl`.

`smoke` runs against the in-repo `lean_project_core/` (core Lean, no Mathlib). `putnam` and
`minif2f` need a built Mathlib project at the matching version — clone the source repo as a
sibling and `lake exe cache get` it (see `data/<name>/SOURCE.md`), or pass `--project`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lean_agent import build_model, load, solve
from lean_agent.benchmarks import PROJECTS
from lean_agent.settings import PROJECT_ROOT


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--benchmark", choices=sorted(PROJECTS), default="smoke")
    p.add_argument("--n", type=int, default=None, help="run the first N problems")
    p.add_argument("--names", nargs="*", default=None, help="explicit problem names")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--project", default=None, help="override the Lean project to compile in")
    p.add_argument("--no-save", action="store_true", help="don't write per-run logs")
    args = p.parse_args(argv)

    problems = load(args.benchmark, names=args.names, project=args.project)
    if args.n is not None and not args.names:
        problems = problems[: args.n]
    if not problems:
        print(f"no problems matched for benchmark={args.benchmark}", file=sys.stderr)
        return 1

    project = problems[0].project
    work_dir = Path(project) / "_work"
    model = build_model()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / f"{args.benchmark}-{stamp}.jsonl"

    print(f"benchmark={args.benchmark}  project={project}  "
          f"problems={len(problems)}  max_steps={args.max_steps}\n")

    n_pass = 0
    with results_path.open("w", encoding="utf-8") as log:
        for i, problem in enumerate(problems, 1):
            r = solve(problem, work_dir=work_dir, model=model,
                      max_steps=args.max_steps, save=not args.no_save)
            log.write(json.dumps(r, ensure_ascii=False) + "\n")
            log.flush()
            n_pass += int(r["passed"])
            flag = "  [statement_changed]" if r.get("statement_changed") else ""
            mark = "PASS" if r["passed"] else f"FAIL ({r['reason']})"
            print(f"[{i}/{len(problems)}] {problem.name:32s} {mark[:90]}{flag}")

    print(f"\n{n_pass}/{len(problems)} passed  ->  {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the agent over a benchmark, or an experiment's conditions, logging every run.

    # benchmarks (smoke needs only a Lean toolchain; minif2f/putnam need a built Mathlib project)
    uv run python run.py --benchmark smoke
    uv run python run.py --benchmark minif2f --n 5

    # the hypothesis experiment: run every condition in benchmarks/data/experiments/<name>/
    uv run python run.py --experiment even_self

Each problem is proved against a pre-warmed Lean REPL environment (its preamble = imports +
definitions, loaded into both Lean and the system prompt). Everything goes under `logs/`: one
folder per run (`run.json` + `transcript.yaml`) plus a `<timestamp>-<label>-summary.jsonl` for
the batch.

The first run builds the Lean REPL (one-time; needs `elan default` set). Mathlib tasks need a
built project — set `LEAN_PROJECT`, or let a temp Mathlib project build on demand (slow first).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from lean_agent import build_model, solve
from lean_agent.lean import Lean, lean_config
from lean_agent.settings import get_settings

from benchmarks import PROJECTS, load, load_experiment


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--benchmark", choices=["smoke", "minif2f", "putnam"])
    group.add_argument("--experiment", help="name of an experiment under benchmarks/data/experiments/")
    p.add_argument("--n", type=int, default=None, help="run the first N problems")
    p.add_argument("--names", nargs="*", default=None, help="explicit problem/condition names")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--no-save", action="store_true", help="don't write per-run logs")
    args = p.parse_args(argv)

    settings = get_settings()
    if args.experiment:
        problems = load_experiment(args.experiment, names=args.names)
        label, project = f"experiment-{args.experiment}", settings.lean_project
    else:
        benchmark = args.benchmark or "smoke"
        problems = load(benchmark, names=args.names)
        label, project = benchmark, PROJECTS.get(benchmark)
    if args.n is not None and not args.names:
        problems = problems[: args.n]
    if not problems:
        print(f"no problems matched for {label}", file=sys.stderr)
        return 1

    print(f"{label}: {len(problems)} problem(s). Building Lean REPL (one-time)…")
    lean = Lean(lean_config(problems[0].preamble, project=project))
    model = build_model()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = settings.log_dir / f"{stamp}-{label}-summary.jsonl"

    n_pass = 0
    with summary_path.open("w", encoding="utf-8") as log:
        for i, problem in enumerate(problems, 1):
            r = solve(problem, lean=lean, model=model, max_steps=args.max_steps, save=not args.no_save)
            log.write(json.dumps(r, ensure_ascii=False) + "\n")
            log.flush()
            n_pass += int(r["passed"])
            mark = "PASS" if r["passed"] else "FAIL"
            extra = f"  ({r['error']})" if r.get("error") else ""
            print(f"[{i}/{len(problems)}] {problem.name:32s} {mark}  "
                  f"steps={r['steps']} tok={r['input_tokens']}+{r['output_tokens']}{extra}")

    print(f"\n{n_pass}/{len(problems)} passed  ->  {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

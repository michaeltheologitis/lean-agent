"""Run the agent over a benchmark, or an experiment's conditions, logging every run.

    # benchmarks (smoke needs only a Lean toolchain; minif2f/putnam need a built Mathlib project)
    uv run python run.py --benchmark smoke
    uv run python run.py --benchmark minif2f --n 5

    # the hypothesis experiment: run every condition in data/experiments/<name>/ and compare
    uv run python run.py --experiment even_self

Each problem is proved against a pre-warmed Lean REPL environment (its preamble = imports +
definitions, loaded into both Lean and the system prompt). Results go to
`results/<label>-<timestamp>.jsonl`; full per-run logs to `logs/<run-folder>/run.md`.

The first run builds the Lean REPL (one-time). Mathlib tasks need a built project — set
`LEAN_PROJECT` to one, or let a temp Mathlib project build on demand (slow first time).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lean_agent import build_model, load, load_experiment, solve
from lean_agent.lean import Lean, lean_config
from lean_agent.settings import PROJECT_ROOT


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--benchmark", choices=["smoke", "minif2f", "putnam"])
    group.add_argument("--experiment", help="name of an experiment under data/experiments/")
    p.add_argument("--n", type=int, default=None, help="run the first N problems")
    p.add_argument("--names", nargs="*", default=None, help="explicit problem/condition names")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--no-save", action="store_true", help="don't write per-run logs")
    args = p.parse_args(argv)

    if args.experiment:
        problems = load_experiment(args.experiment, names=args.names)
        label = f"experiment-{args.experiment}"
    else:
        benchmark = args.benchmark or "smoke"
        problems = load(benchmark, names=args.names)
        label = benchmark
    if args.n is not None and not args.names:
        problems = problems[: args.n]
    if not problems:
        print(f"no problems matched for {label}", file=sys.stderr)
        return 1

    print(f"{label}: {len(problems)} problem(s). Building Lean REPL (one-time)…")
    lean = Lean(lean_config(problems[0].benchmark, problems[0].preamble))
    model = build_model()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / f"{label}-{stamp}.jsonl"

    n_pass = 0
    with results_path.open("w", encoding="utf-8") as log:
        for i, problem in enumerate(problems, 1):
            r = solve(problem, lean=lean, model=model, max_steps=args.max_steps, save=not args.no_save)
            log.write(json.dumps(r, ensure_ascii=False) + "\n")
            log.flush()
            n_pass += int(r["passed"])
            mark = "PASS" if r["passed"] else "FAIL"
            extra = f"  ({r['error']})" if r.get("error") else ""
            print(f"[{i}/{len(problems)}] {problem.name:32s} {mark}  "
                  f"steps={r['steps']} tok={r['input_tokens']}+{r['output_tokens']}{extra}")

    print(f"\n{n_pass}/{len(problems)} passed  ->  {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

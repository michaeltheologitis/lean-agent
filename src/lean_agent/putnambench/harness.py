"""
Benchmark harness: run a proof agent against PutnamBench and score it.

Your agent is any callable. Two supported shapes:

  generate(problem) -> proof_str
      one-shot: given a Problem, return a proof body (what replaces `sorry`).

  generate(problem, feedback=None) -> proof_str
      iterative: when feedback (the last Lean error) is passed, return a revised
      proof. This matches an agent that reads compiler output and proposes the
      next step. Detected automatically via the function signature.

Scoring:
  pass@k    -> run up to k independent attempts, pass if any compiles.
  repair    -> within an attempt, feed Lean errors back up to `repair_rounds`
               times before counting the attempt as failed.

Results stream to a JSONL file so a long run is resumable/inspectable.
"""

from __future__ import annotations

import inspect
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .putnam_loader import Problem, load_problems
from .verify import verify_proof, VerifyResult


def _accepts_feedback(fn: Callable) -> bool:
    try:
        return "feedback" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def run_benchmark(
    agent: Callable,
    repo_path: str | Path,
    out_path: str | Path = "results.jsonl",
    k: int = 1,
    repair_rounds: int = 0,
    timeout: int = 300,
    fill_answers: bool = True,
    resume: bool = True,
    **filter_kw,
) -> dict:
    """
    agent: callable(problem) -> proof, or callable(problem, feedback) -> proof.
    k: pass@k attempts per problem.
    repair_rounds: feedback iterations within an attempt (needs feedback-aware agent).
    filter_kw: passed to load_problems (tags=, years=, task_type=, names=).
    """
    problems = load_problems(repo_path, **filter_kw)
    out_path = Path(out_path)
    use_feedback = _accepts_feedback(agent) and repair_rounds > 0

    done: set[str] = set()
    if resume and out_path.exists():
        for line in out_path.read_text().splitlines():
            try:
                done.add(json.loads(line)["problem"])
            except Exception:
                pass

    n_pass = n_total = 0
    t0 = time.time()
    with out_path.open("a", encoding="utf-8") as log:
        for prob in problems:
            if prob.name in done:
                continue
            n_total += 1
            rec = _attempt_problem(
                agent, prob, repo_path, k, repair_rounds,
                use_feedback, timeout, fill_answers,
            )
            n_pass += int(rec["passed"])
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log.flush()
            mark = "PASS" if rec["passed"] else rec["status"]
            print(f"[{n_pass}/{n_total}] {prob.name:24s} {mark}")

    prev = len(done)
    total = prev + n_total
    summary = {
        "problems_attempted": n_total,
        "passed_this_run": n_pass,
        "already_done": prev,
        "pass_rate_this_run": round(n_pass / n_total, 4) if n_total else None,
        "k": k,
        "repair_rounds": repair_rounds,
        "elapsed_sec": round(time.time() - t0, 1),
        "results_file": str(out_path),
    }
    print("\n" + json.dumps(summary, indent=2))
    return summary


def _attempt_problem(
    agent, prob: Problem, repo_path, k, repair_rounds,
    use_feedback, timeout, fill_answers,
) -> dict:
    attempts = []
    for attempt_i in range(k):
        feedback = None
        for round_i in range(repair_rounds + 1):
            proof = agent(prob, feedback=feedback) if use_feedback else agent(prob)
            res: VerifyResult = verify_proof(
                prob, proof, repo_path, timeout=timeout, fill_answers=fill_answers,
            )
            attempts.append({
                "attempt": attempt_i,
                "round": round_i,
                "status": res.status,
                "proof": proof,
                "output": res.output if not res.ok else "",
            })
            if res.ok:
                return {
                    "problem": prob.name,
                    "tags": prob.tags,
                    "task_type": prob.task_type,
                    "passed": True,
                    "status": "pass",
                    "winning_proof": proof,
                    "n_attempts": len(attempts),
                    "attempts": attempts,
                }
            if not use_feedback:
                break
            feedback = res.output

    return {
        "problem": prob.name,
        "tags": prob.tags,
        "task_type": prob.task_type,
        "passed": False,
        "status": attempts[-1]["status"] if attempts else "error",
        "winning_proof": None,
        "n_attempts": len(attempts),
        "attempts": attempts,
    }


def score_report(results_path: str | Path) -> dict:
    """Aggregate a results.jsonl into overall + per-tag + per-type pass rates."""
    import collections
    recs = [json.loads(l) for l in Path(results_path).read_text().splitlines() if l.strip()]
    by_tag = collections.defaultdict(lambda: [0, 0])
    by_type = collections.defaultdict(lambda: [0, 0])
    npass = sum(r["passed"] for r in recs)
    for r in recs:
        for t in r.get("tags", []):
            by_tag[t][0] += r["passed"]; by_tag[t][1] += 1
        by_type[r.get("task_type", "?")][0] += r["passed"]
        by_type[r.get("task_type", "?")][1] += 1
    return {
        "n": len(recs),
        "passed": npass,
        "pass_rate": round(npass / len(recs), 4) if recs else None,
        "by_tag": {t: f"{a}/{b} ({a/b:.0%})" for t, (a, b) in sorted(by_tag.items())},
        "by_type": {t: f"{a}/{b} ({a/b:.0%})" for t, (a, b) in by_type.items()},
    }

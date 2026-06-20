"""Backfill clean_log.json / clean_log.md for runs saved before the clean-log
hook existed (or by a process that imported settings.py before the hook).

Clean logs are a re-rendering of data already captured in run.json, so no run
needs to be re-executed. For each run dir that has run.json but no clean_log.json,
this reconstructs the clean log from run.json and writes it using clean.py's own
renderer, so backfilled logs match natively-generated ones.

Run:  uv run python experiments/backfill_clean_logs.py [logs_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lean_agent.clean import _extract_python_calls, build_clean_markdown

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOGS = ROOT / "logs"
# Tool names whose calls we surface in the clean log (agent + ours).
TOOL_NAMES = {"write_and_check", "lean_goal", "final_answer"}


def clean_log_from_run(run: dict) -> dict:
    """Reconstruct the clean-log dict from a saved run.json payload."""
    logs = run.get("logs", {})
    steps_out = []
    for i, step in enumerate(logs.get("steps", []), start=1):
        msgs = step.get("messages", [])
        # create_logs() appends model_output as the final assistant message.
        model_output = ""
        if msgs and msgs[-1].get("role") == "assistant":
            model_output = msgs[-1].get("content", "") or ""
        usage = step.get("usage")
        if not (model_output or usage):
            continue
        out = {
            "step": i,
            "model_output": model_output,
            "python_calls": _extract_python_calls(model_output, TOOL_NAMES),
        }
        if usage is not None:
            out["usage"] = usage
        steps_out.append(out)

    return {
        "user_input": run.get("prompt", ""),
        "steps": steps_out,
        "final_answer": run.get("answer", ""),
        "total_usage": logs.get("total_usage", {}),
    }


def main() -> None:
    logs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOGS
    run_files = sorted(logs_dir.glob("*/run.json"))
    written = skipped = 0
    for rf in run_files:
        run_dir = rf.parent
        if (run_dir / "clean_log.json").exists():
            skipped += 1
            continue
        run = json.loads(rf.read_text(encoding="utf-8"))
        manifest = run.get("manifest", {})
        clean_log = clean_log_from_run(run)
        clean_payload = {"manifest": manifest, **clean_log}
        (run_dir / "clean_log.json").write_text(
            json.dumps(clean_payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (run_dir / "clean_log.md").write_text(
            build_clean_markdown(clean_log, manifest), encoding="utf-8"
        )
        written += 1
    print(f"backfilled {written} run(s); skipped {skipped} that already had clean logs")


if __name__ == "__main__":
    main()

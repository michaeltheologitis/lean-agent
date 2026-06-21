"""Run logging — what the model saw and did.

smolagents already records each step structurally — the code the agent ran
(`step.code_action`), the tool output (`step.observations`), the per-step token usage — so
we just read those fields; no parsing. Each run writes two files:

    run.json  — the full structured record (manifest + every step + total usage), straight
                from smolagents' own `agent.memory.get_full_steps()`.
    run.md    — a readable per-step view (the thought, the code it ran, the Lean output,
                token usage). The file you read after a run.

The manifest carries the run's identity (model / benchmark / problem); the log-folder name
stays opaque (`<timestamp>-<run_id>`). Runs accumulate, never overwrite.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .settings import get_settings


def _text(value) -> str:
    """ChatMessage content is a string or a list of `{type, text}` parts — flatten to text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            p.get("text", "") for p in value if isinstance(p, dict) and p.get("type") == "text"
        )
    return "" if value is None else str(value)


def save_run(agent, answer, *, run_id: str | None = None, manifest: dict | None = None) -> Path:
    """Persist a finished agent run (run.json + run.md) and return the run directory."""
    settings = get_settings()
    run_id = run_id or secrets.token_hex(3)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = settings.log_dir / f"{ts}-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    total = agent.monitor.get_total_token_counts()
    meta = {"run_id": run_id, "timestamp": ts, "model_id": settings.model_id, **(manifest or {})}
    usage = {
        "input_tokens": total.input_tokens,
        "output_tokens": total.output_tokens,
        "total_tokens": total.total_tokens,
    }

    (run_dir / "run.json").write_text(
        json.dumps(
            {"manifest": meta, "answer": str(answer), "usage": usage,
             "steps": agent.memory.get_full_steps()},
            indent=2, ensure_ascii=False, default=str,
        ),
        encoding="utf-8",
    )
    (run_dir / "run.md").write_text(_markdown(agent, answer, meta, usage), encoding="utf-8")
    return run_dir


def _markdown(agent, answer, meta, usage) -> str:
    head = " · ".join(f"{k}: {v}" for k, v in meta.items() if k != "timestamp")
    lines = [f"# {meta['run_id']}", "", head, ""]
    for step in agent.memory.steps:
        task = getattr(step, "task", None)
        if task:  # the initial TaskStep
            lines += ["## Task", "", _text(task), ""]
            continue
        output = _text(getattr(step, "model_output", "") or "")
        code = getattr(step, "code_action", None)
        observations = getattr(step, "observations", None)
        tu = getattr(step, "token_usage", None)
        lines += [f"## Step {getattr(step, 'step_number', '?')}", ""]
        if output:
            lines += ["**Model output**", "", output, ""]
        if code:
            lines += ["**Code run**", "", "```python", str(code).strip(), "```", ""]
        if observations:
            lines += ["**Lean output**", "", "```", _text(observations).strip(), "```", ""]
        if tu:
            lines += [f"_tokens — in: {tu.input_tokens}, out: {tu.output_tokens}_", ""]
    lines += [
        "## Final answer", "", str(answer), "",
        f"_total tokens — in: {usage['input_tokens']}, out: {usage['output_tokens']}_", "",
    ]
    return "\n".join(lines)

"""Run logging — what the model saw and did.

smolagents records each step structurally, so we read its fields directly (no parsing). Each
run writes two files into `logs/<timestamp>-<run_id>/`:

    run.json        the full structured record (manifest + every step + usage), straight from
                    `agent.memory.get_full_steps()` — for programmatic analysis.
    transcript.yaml the top-down conversation lineage as a list of turns
                    (system / user / assistant / tool-call / tool-response) — the file you read
                    to trace what happened, in order.

The manifest carries the run's identity (model / benchmark / problem); the folder name stays
opaque (`<timestamp>-<run_id>`). Runs accumulate, never overwrite.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .settings import get_settings


class _ReadableDumper(yaml.SafeDumper):
    """YAML dumper that renders multi-line strings as literal blocks (`|`) instead of
    quoted strings full of `\\n` and line-continuation backslashes."""


def _represent_str(dumper, data):
    if "\n" in data:
        # rstrip each line so PyYAML can use literal block style (trailing spaces force quotes)
        data = "\n".join(line.rstrip() for line in data.split("\n"))
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_ReadableDumper.add_representer(str, _represent_str)


def _text(value) -> str:
    """ChatMessage content is a string or a list of `{type, text}` parts — flatten to text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            p.get("text", "") for p in value if isinstance(p, dict) and p.get("type") == "text"
        )
    return "" if value is None else str(value)


def _messages(agent) -> list[dict[str, str]]:
    """The run as a flat, ordered list of turns, from smolagents' own `to_messages()`.
    Roles are the raw `MessageRole` values: system / user / assistant / tool-call /
    tool-response."""
    raw = list(agent.memory.system_prompt.to_messages())
    for step in agent.memory.steps:
        raw.extend(step.to_messages())
    out = []
    for m in raw:
        role = m.role.value
        content = _text(m.content)
        if role == "tool-call":
            # the tool-call message is a repr of the call, so newlines in the Lean `code`
            # argument come out as literal `\n` — turn them back into real line breaks.
            content = content.replace("\\n", "\n")
        out.append({"role": role, "content": content})
    return out


def save_run(agent, answer, *, run_id: str | None = None, manifest: dict | None = None,
             proof: str | None = None) -> Path:
    """Persist a finished agent run (run.json + transcript.yaml) and return the run directory.

    If `proof` is given (the winning proof, preamble included), also write a self-contained,
    re-compilable `proof.lean`."""
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
    transcript = {**meta, "answer": str(answer), "usage": usage, "messages": _messages(agent)}
    with (run_dir / "transcript.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(transcript, f, Dumper=_ReadableDumper, sort_keys=False,
                  allow_unicode=True, default_flow_style=False, width=10 ** 9)
    if proof:
        (run_dir / "proof.lean").write_text(
            proof if proof.endswith("\n") else proof + "\n", encoding="utf-8"
        )
    return run_dir

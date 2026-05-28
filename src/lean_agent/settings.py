"""Settings + run-output persistence.

A finished agent run is written to `<log_dir>/<timestamp>-<run_id>/`:

    run.json         - {manifest, prompt, answer, logs} — primary structured
                       record. `logs` is built by `create_logs()`: per-step
                       token usage and the exact messages sent to / received
                       from the LLM, plus a top-level total_usage. Built from
                       smolagents-native fields (step.token_usage,
                       step.model_input_messages, step.model_output,
                       agent.monitor).
    transcript.yaml  - sanitized chat-message view derived from
                       `step.to_messages()`: system / user / assistant /
                       tool-call / tool-response, ... Easy to read linearly.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Runtime configuration.

    Only secrets come from the environment. Everything else is a default here
    — edit the dataclass to change them. `api_key` / `api_base` mirror
    smolagents' `OpenAIServerModel` kwargs so swapping providers (hosted
    OpenAI, vLLM, llama.cpp, ...) is just a default change.
    """
    api_key: str | None = None
    model_id: str = "gpt-5.4-nano"
    api_base: str | None = None  # None = hosted OpenAI; set to e.g. "http://localhost:8000/v1" for vLLM
    log_dir: Path = PROJECT_ROOT / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    settings = Settings(api_key=os.getenv("OPENAI_API_KEY") or None)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings


# --- run output ---------------------------------------------------------------


def _content_to_text(content: Any) -> str:
    """ChatMessage content is either a string or a list of `{type, text|image}`
    parts. Collapse the text parts into a single string; ignore non-text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


def create_logs(agent: Any) -> dict[str, Any]:
    """Extract per-step messages + usage from a finished CodeAgent.

    Skips `TaskStep` (no LLM call, no token_usage). For each step that did
    call the model, records the exact input messages sent and the assistant
    output, plus that step's token usage. Total usage comes from the agent's
    own monitor (covers every LLM call in the run).
    """
    steps_data: list[dict[str, Any]] = []
    for step in agent.memory.steps:
        if getattr(step, "token_usage", None) is None:
            continue

        messages = [
            {"role": msg.role.value, "content": _content_to_text(msg.content)}
            for msg in (step.model_input_messages or [])
        ]
        if step.model_output is not None:
            messages.append({"role": "assistant", "content": step.model_output})

        steps_data.append({
            "usage": asdict(step.token_usage),
            "messages": messages,
        })

    total = agent.monitor.get_total_token_counts()
    return {
        "total_usage": {
            "input_tokens": total.input_tokens,
            "output_tokens": total.output_tokens,
            "total_tokens": total.total_tokens,
        },
        "steps": steps_data,
    }


def build_transcript(agent: Any) -> list[dict[str, str]]:
    """Sanitized chat-message view of a run, derived from smolagents'
    own `step.to_messages()`. Roles are the raw values of smolagents'
    `MessageRole` enum (`system`, `user`, `assistant`, `tool-call`,
    `tool-response`)."""
    raw = list(agent.memory.system_prompt.to_messages())
    for step in agent.memory.steps:
        raw.extend(step.to_messages())
    return [{"role": m.role.value, "content": _content_to_text(m.content)} for m in raw]


def save_run(agent: Any, answer: Any, *, run_id: str | None = None) -> Path:
    """Persist a finished agent run and return the run directory.

    `run_id` defaults to a fresh random hex; pass one explicitly to label a
    specific experiment. Everything else (model_id, log_dir) comes from
    `get_settings()`. The prompt is read from `agent.memory.steps[0].task`.
    """
    settings = get_settings()
    run_id = run_id or secrets.token_hex(3)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = settings.log_dir / f"{timestamp}-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "timestamp": timestamp,
        "model_id": settings.model_id,
    }
    prompt = agent.memory.steps[0].task if agent.memory.steps else ""

    payload = {
        "manifest": manifest,
        "prompt": prompt,
        "answer": str(answer),
        "logs": create_logs(agent),
    }
    (run_dir / "run.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    transcript = {
        **manifest,
        "prompt": prompt,
        "final_answer": str(answer),
        "messages": build_transcript(agent),
    }
    with (run_dir / "transcript.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(transcript, f, sort_keys=False, allow_unicode=True, width=100)

    return run_dir

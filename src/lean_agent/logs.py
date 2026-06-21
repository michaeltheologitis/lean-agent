"""Run-output persistence — the product of this harness.

A finished agent run is written to `<log_dir>/<timestamp>-<run_id>/` with four files:

    run.json         {manifest, prompt, answer, logs} — the raw structured record.
                     `logs` carries per-step token usage + the exact messages sent to /
                     received from the model, plus a top-level total_usage. Built from
                     smolagents-native fields.
    transcript.yaml  sanitized linear chat view (system / user / assistant / tool-call /
                     tool-response) derived from `step.to_messages()`. Easy to read top-down.
    clean_log.json   the readable per-step distillation (model output, tool calls, usage).
    clean_log.md     the same, rendered as Markdown — the file you read after a run.

`save_run` writes all four. The manifest carries the run's identity (model, benchmark,
problem); the log-folder name stays opaque (`<timestamp>-<run_id>`).
"""

from __future__ import annotations

import ast
import json
import re
import secrets
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .settings import get_settings


def _content_to_text(content: Any) -> str:
    """ChatMessage content is either a string or a list of `{type, text|image}` parts.
    Collapse the text parts into one string; ignore non-text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


# --- raw record ---------------------------------------------------------------


def create_logs(agent: Any) -> dict[str, Any]:
    """Extract per-step messages + usage from a finished CodeAgent.

    Skips steps with no LLM call (no token_usage). For each model-calling step, records the
    exact input messages and the assistant output, plus that step's usage. Total usage comes
    from the agent's monitor (covers every LLM call in the run).
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
    """Sanitized chat-message view of a run, from smolagents' own `step.to_messages()`.
    Roles are the raw `MessageRole` values (system / user / assistant / tool-call /
    tool-response)."""
    raw = list(agent.memory.system_prompt.to_messages())
    for step in agent.memory.steps:
        raw.extend(step.to_messages())
    return [{"role": m.role.value, "content": _content_to_text(m.content)} for m in raw]


# --- clean record (readable per-step distillation) ----------------------------
# Surfaces the model output, the tool calls it actually made, and token usage per step.


def _tool_names(agent: Any) -> set[str]:
    tools = getattr(agent, "tools", None)
    if isinstance(tools, dict):
        return set(tools)
    if tools is None:
        return set()
    return {
        name
        for tool in tools
        if (name := getattr(tool, "name", None) or getattr(tool, "__name__", None))
    }


def _extract_python_calls(text: str, tool_names: set[str]) -> list[str]:
    calls: list[str] = []
    seen: set[str] = set()
    blocks = re.findall(
        r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
    ) or [text]

    for block in blocks:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            calls.extend(_extract_known_tool_calls(block, tool_names))
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            else:
                continue
            if tool_names and call_name not in tool_names:
                continue
            call = ast.unparse(node)
            if call not in seen:
                seen.add(call)
                calls.append(call)
    return calls


def _extract_known_tool_calls(text: str, tool_names: set[str]) -> list[str]:
    if not tool_names:
        return []
    names = "|".join(re.escape(name) for name in sorted(tool_names, key=len, reverse=True))
    pattern = rf"\b({names})\s*\(([^()]*)\)"
    return [f"{name}({args.strip()})" for name, args in re.findall(pattern, text)]


def _normalize_call(call: str) -> str:
    try:
        return ast.unparse(ast.parse(call, mode="eval"))
    except SyntaxError:
        return call


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_call(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _format_call(name: str, arguments: Any = None) -> str:
    if arguments in (None, "", {}):
        return f"{name}()"
    if isinstance(arguments, str):
        stripped = arguments.strip()
        try:
            arguments = json.loads(stripped)
        except json.JSONDecodeError:
            return f"{name}({stripped})" if stripped else f"{name}()"
    if isinstance(arguments, dict):
        args = ", ".join(f"{key}={value!r}" for key, value in arguments.items())
        return f"{name}({args})"
    if isinstance(arguments, (list, tuple)):
        args = ", ".join(repr(value) for value in arguments)
        return f"{name}({args})"
    return f"{name}({arguments!r})"


def _extract_calls_from_mapping(value: dict[str, Any], tool_names: set[str]) -> list[str]:
    if "function" in value and isinstance(value["function"], dict):
        function = value["function"]
        name = function.get("name")
        if isinstance(name, str) and (not tool_names or name in tool_names):
            return [_format_call(name, function.get("arguments"))]

    name = (
        value.get("name") or value.get("tool_name")
        or value.get("function_name") or value.get("tool")
    )
    if isinstance(name, str) and (not tool_names or name in tool_names):
        arguments = (
            value.get("arguments") or value.get("args") or value.get("kwargs")
            or value.get("inputs") or value.get("input")
        )
        return [_format_call(name, arguments)]

    calls: list[str] = []
    for nested in value.values():
        calls.extend(_extract_calls_from_value(nested, tool_names))
    return calls


def _extract_calls_from_value(value: Any, tool_names: set[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return _extract_calls_from_mapping(value, tool_names)
    if isinstance(value, list):
        calls: list[str] = []
        for item in value:
            calls.extend(_extract_calls_from_value(item, tool_names))
        return calls
    if isinstance(value, str):
        stripped = value.strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return _extract_python_calls(stripped, tool_names)
        return _extract_calls_from_value(parsed, tool_names)
    return []


def _step_messages(step: Any) -> list[Any]:
    try:
        return list(step.to_messages())
    except Exception:
        return []


def _step_python_calls(step: Any, model_output_text: str, tool_names: set[str]) -> list[str]:
    executed_calls: list[str] = []
    for message in _step_messages(step):
        role = getattr(getattr(message, "role", None), "value", "")
        if role == "tool-call":
            executed_calls.extend(_extract_calls_from_value(message.content, tool_names))
    for field in ("tool_calls", "tool_call", "action", "code_action"):
        executed_calls.extend(_extract_calls_from_value(getattr(step, field, None), tool_names))

    executed_calls = _dedupe(executed_calls)
    if executed_calls:
        return executed_calls
    if model_output_text:
        return _dedupe(_extract_python_calls(model_output_text, tool_names))
    return []


def create_clean_logs(agent: Any, answer: Any) -> dict[str, Any]:
    """Build the compact log from visible model output and tool activity."""
    prompt = agent.memory.steps[0].task if agent.memory.steps else ""
    tool_names = _tool_names(agent)
    steps: list[dict[str, Any]] = []

    for index, step in enumerate(agent.memory.steps, start=1):
        model_output = getattr(step, "model_output", None)
        model_output_text = _content_to_text(model_output) if model_output is not None else ""
        python_calls = _step_python_calls(step, model_output_text, tool_names)
        usage = getattr(step, "token_usage", None)

        if not any((model_output_text, python_calls, usage)):
            continue

        step_data: dict[str, Any] = {
            "step": index,
            "model_output": model_output_text,
            "python_calls": python_calls,
        }
        if usage is not None:
            step_data["usage"] = asdict(usage)
        steps.append(step_data)

    total = agent.monitor.get_total_token_counts()
    return {
        "user_input": prompt,
        "steps": steps,
        "final_answer": str(answer),
        "total_usage": {
            "input_tokens": total.input_tokens,
            "output_tokens": total.output_tokens,
            "total_tokens": total.total_tokens,
        },
    }


def build_clean_markdown(clean_log: dict[str, Any], manifest: dict[str, str]) -> str:
    lines = [
        f"# {manifest.get('run_id', 'run')}",
        "",
        "## User Input",
        "",
        clean_log["user_input"] or "_No prompt recorded._",
        "",
    ]
    for step in clean_log["steps"]:
        lines.extend([
            f"## Step {step['step']}", "", "### Model Output", "",
            step["model_output"] or "_No model output recorded._", "",
        ])
        if step["python_calls"]:
            lines.extend(["### Python Calls", "", "```python"])
            lines.extend(step["python_calls"])
            lines.extend(["```", ""])
    lines.extend(["## Final Answer", "", clean_log["final_answer"], ""])
    return "\n".join(lines)


# --- the one entry point ------------------------------------------------------


def save_run(
    agent: Any,
    answer: Any,
    *,
    run_id: str | None = None,
    extra_manifest: dict[str, Any] | None = None,
) -> Path:
    """Persist a finished agent run (all four files) and return the run directory.

    `run_id` defaults to a fresh random hex; pass one to label a specific experiment.
    `extra_manifest` is merged into the manifest — use it to record run identity
    (benchmark, problem) that the opaque folder name deliberately omits.
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
        **(extra_manifest or {}),
    }
    prompt = agent.memory.steps[0].task if agent.memory.steps else ""

    payload = {
        "manifest": manifest,
        "prompt": prompt,
        "answer": str(answer),
        "logs": create_logs(agent),
    }
    (run_dir / "run.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    transcript = {
        **manifest,
        "prompt": prompt,
        "final_answer": str(answer),
        "messages": build_transcript(agent),
    }
    with (run_dir / "transcript.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(transcript, f, sort_keys=False, allow_unicode=True, width=100)

    clean_log = create_clean_logs(agent, answer)
    (run_dir / "clean_log.json").write_text(
        json.dumps({"manifest": manifest, **clean_log}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (run_dir / "clean_log.md").write_text(
        build_clean_markdown(clean_log, manifest), encoding="utf-8"
    )

    return run_dir

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


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
        r"```(?:python|py)?\s*\n(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
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


def _is_explicit_call(call: str) -> bool:
    try:
        parsed = ast.parse(call, mode="eval")
    except SyntaxError:
        return True
    if not isinstance(parsed.body, ast.Call):
        return True

    for node in ast.walk(parsed):
        if isinstance(node, ast.Name) and node.id in {"n", "text", "value", "from_unit", "to_unit"}:
            return False
    return True


def _extract_calls_from_mapping(value: dict[str, Any], tool_names: set[str]) -> list[str]:
    if "function" in value and isinstance(value["function"], dict):
        function = value["function"]
        name = function.get("name")
        if isinstance(name, str) and (not tool_names or name in tool_names):
            return [_format_call(name, function.get("arguments"))]

    name = (
        value.get("name")
        or value.get("tool_name")
        or value.get("function_name")
        or value.get("tool")
    )
    if isinstance(name, str) and (not tool_names or name in tool_names):
        arguments = (
            value.get("arguments")
            or value.get("args")
            or value.get("kwargs")
            or value.get("inputs")
            or value.get("input")
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

    executed_calls = [call for call in _dedupe(executed_calls) if _is_explicit_call(call)]
    if executed_calls:
        return executed_calls

    if model_output_text:
        return [
            call
            for call in _dedupe(_extract_python_calls(model_output_text, tool_names))
            if _is_explicit_call(call)
        ]
    return []


def create_clean_logs(agent: Any, answer: Any) -> dict[str, Any]:
    """Build a compact log from visible model output and tool activity."""
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
        f"# {manifest['run_id']}",
        "",
        "## User Input",
        "",
        clean_log["user_input"] or "_No prompt recorded._",
        "",
    ]

    for step in clean_log["steps"]:
        lines.extend([
            f"## Step {step['step']}",
            "",
            "### Model Output",
            "",
            step["model_output"] or "_No model output recorded._",
            "",
        ])

        if step["python_calls"]:
            lines.extend(["### Python Calls", "", "```python"])
            lines.extend(step["python_calls"])
            lines.extend(["```", ""])

    lines.extend(["## Final Answer", "", clean_log["final_answer"], ""])
    return "\n".join(lines)


def write_clean_logs(
    agent: Any,
    answer: Any,
    run_dir: Path,
    manifest: dict[str, str],
) -> None:
    clean_log = create_clean_logs(agent, answer)
    clean_payload = {"manifest": manifest, **clean_log}
    (run_dir / "clean_log.json").write_text(
        json.dumps(clean_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (run_dir / "clean_log.md").write_text(
        build_clean_markdown(clean_log, manifest),
        encoding="utf-8",
    )

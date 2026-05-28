"""End-to-end test: build an agent, run a real prompt, persist + inspect logs.

This test hits the real OpenAI API and is skipped when no key is configured.
"""

from __future__ import annotations

import json
import os

import pytest
import yaml
from smolagents import CodeAgent, OpenAIServerModel

from lean_agent import ALL_TOOLS, save_run
from lean_agent import settings as settings_module
from lean_agent.settings import Settings


pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)


def test_agent_run_and_logs_are_reasonable(monkeypatch, tmp_path):
    # Stub get_settings() to drop log output into a temp dir but keep the real
    # api_key / model_id / api_base from the user's environment.
    settings_module.get_settings.cache_clear()
    real = settings_module.get_settings()
    stub = Settings(
        api_key=real.api_key,
        model_id=real.model_id,
        api_base=real.api_base,
        log_dir=tmp_path,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: stub)

    model = OpenAIServerModel(
        model_id=stub.model_id,
        api_key=stub.api_key,
        api_base=stub.api_base,
    )
    agent = CodeAgent(tools=ALL_TOOLS, model=model)

    prompt = "Use the fibonacci tool to compute the 10th Fibonacci number."
    answer = agent.run(prompt)

    # 1. Agent produced the expected answer (F(10) = 55).
    assert "55" in str(answer)

    # 2. save_run created a per-run directory with two files. Pass an explicit
    # run_id so we can assert against it.
    run_dir = save_run(agent, answer, run_id="t-fib10")
    assert run_dir.exists() and run_dir.parent == tmp_path
    assert run_dir.name.endswith("-t-fib10")
    assert {p.name for p in run_dir.iterdir()} == {"run.json", "transcript.yaml"}

    # 3. run.json has {manifest, prompt, answer, logs} with reasonable contents.
    data = json.loads((run_dir / "run.json").read_text())
    assert set(data) == {"manifest", "prompt", "answer", "logs"}

    assert data["manifest"]["model_id"] == stub.model_id
    assert data["manifest"]["run_id"] == "t-fib10"
    assert "timestamp" in data["manifest"]
    assert data["prompt"] == prompt
    assert "55" in data["answer"]

    logs = data["logs"]
    total = logs["total_usage"]
    assert total["input_tokens"] > 0
    assert total["output_tokens"] > 0
    assert total["total_tokens"] == total["input_tokens"] + total["output_tokens"]

    assert logs["steps"], "expected at least one LLM-call step"
    step = logs["steps"][0]
    assert step["usage"]["input_tokens"] > 0
    assert step["messages"][0]["role"] == "system"
    assert any(m["role"] == "user" and prompt in m["content"] for m in step["messages"])
    assert step["messages"][-1]["role"] == "assistant"
    assert "fibonacci" in step["messages"][-1]["content"].lower()

    # Per-step usage sums to the agent monitor total.
    sum_input = sum(s["usage"]["input_tokens"] for s in logs["steps"])
    sum_output = sum(s["usage"]["output_tokens"] for s in logs["steps"])
    assert sum_input == total["input_tokens"]
    assert sum_output == total["output_tokens"]

    # 4. transcript.yaml is the sanitized chat view.
    transcript = yaml.safe_load((run_dir / "transcript.yaml").read_text())
    assert transcript["model_id"] == stub.model_id
    assert transcript["prompt"] == prompt
    assert "55" in transcript["final_answer"]
    roles = [m["role"] for m in transcript["messages"]]
    assert roles[0] == "system"
    assert "user" in roles
    assert "assistant" in roles
    assert any(r in {"tool-response", "tool-call"} for r in roles)


def test_save_run_auto_run_id(monkeypatch, tmp_path):
    """When run_id is not supplied, save_run generates a hex one."""
    import re

    settings_module.get_settings.cache_clear()
    real = settings_module.get_settings()
    stub = Settings(
        api_key=real.api_key,
        model_id=real.model_id,
        api_base=real.api_base,
        log_dir=tmp_path,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: stub)

    model = OpenAIServerModel(
        model_id=stub.model_id, api_key=stub.api_key, api_base=stub.api_base,
    )
    agent = CodeAgent(tools=ALL_TOOLS, model=model)
    answer = agent.run("What is 2 + 3?")

    run_dir = save_run(agent, answer)
    data = json.loads((run_dir / "run.json").read_text())
    assert re.fullmatch(r"[0-9a-f]{6}", data["manifest"]["run_id"])

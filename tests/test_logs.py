"""Tests for run persistence + clean logs, driven by a minimal fake agent (no API)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import yaml

from lean_agent import logs as logs_module
from lean_agent.settings import Settings


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


class Role:
    def __init__(self, value):
        self.value = value


class Msg:
    def __init__(self, role, content):
        self.role = Role(role)
        self.content = content


class Step:
    def __init__(self, *, task=None, usage=None, inputs=None, output=None, messages=None):
        self.task = task
        self.token_usage = usage
        self.model_input_messages = inputs or []
        self.model_output = output
        self._messages = messages or []

    def to_messages(self):
        return self._messages


class Total:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens, self.total_tokens = i, o, i + o


class Monitor:
    def __init__(self, i, o):
        self._t = Total(i, o)

    def get_total_token_counts(self):
        return self._t


class SystemPrompt:
    def __init__(self, messages):
        self._m = messages

    def to_messages(self):
        return self._m


class Memory:
    def __init__(self, steps, system_prompt):
        self.steps = steps
        self.system_prompt = system_prompt


class FakeAgent:
    def __init__(self, memory, monitor, tools):
        self.memory = memory
        self.monitor = monitor
        self.tools = tools


def _agent():
    task_step = Step(task="Prove smoke_true.")
    action_step = Step(
        usage=Usage(100, 40, 140),
        inputs=[Msg("system", "you are a prover"), Msg("user", "Prove smoke_true.")],
        output="I'll fill it in.\n```python\nwrite_and_check('theorem smoke_true : True := by trivial')\n```",
        messages=[Msg("assistant", "calling tool"), Msg("tool-response", "status: compiled successfully")],
    )
    memory = Memory([task_step, action_step], SystemPrompt([Msg("system", "you are a prover")]))
    return FakeAgent(memory, Monitor(100, 40), {"write_and_check": None, "final_answer": None})


def test_save_run_writes_four_files(monkeypatch, tmp_path):
    stub = Settings(api_key=None, model_id="gpt-5.4-nano",
                    api_base="https://api.openai.com/v1", log_dir=tmp_path)
    monkeypatch.setattr(logs_module, "get_settings", lambda: stub)

    run_dir = logs_module.save_run(
        _agent(), "done", run_id="t-logtest",
        extra_manifest={"benchmark": "smoke", "problem": "smoke_true", "passed": True},
    )
    assert run_dir.parent == tmp_path and run_dir.name.endswith("-t-logtest")
    assert {p.name for p in run_dir.iterdir()} == {
        "run.json", "transcript.yaml", "clean_log.json", "clean_log.md"
    }


def test_run_json_structure_and_manifest(monkeypatch, tmp_path):
    stub = Settings(api_key=None, model_id="gpt-5.4-nano",
                    api_base="https://api.openai.com/v1", log_dir=tmp_path)
    monkeypatch.setattr(logs_module, "get_settings", lambda: stub)

    run_dir = logs_module.save_run(
        _agent(), "done", run_id="t-logtest",
        extra_manifest={"benchmark": "smoke", "passed": True},
    )
    data = json.loads((run_dir / "run.json").read_text())
    assert set(data) == {"manifest", "prompt", "answer", "logs"}
    assert data["manifest"]["benchmark"] == "smoke"
    assert data["manifest"]["model_id"] == "gpt-5.4-nano"
    assert data["prompt"] == "Prove smoke_true."
    total = data["logs"]["total_usage"]
    assert total == {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}
    assert len(data["logs"]["steps"]) == 1  # the TaskStep (no usage) is skipped


def test_clean_log_shows_output_and_calls(monkeypatch, tmp_path):
    stub = Settings(api_key=None, model_id="gpt-5.4-nano",
                    api_base="https://api.openai.com/v1", log_dir=tmp_path)
    monkeypatch.setattr(logs_module, "get_settings", lambda: stub)

    run_dir = logs_module.save_run(_agent(), "done", run_id="t-logtest")
    md = (run_dir / "clean_log.md").read_text()
    assert "## Final Answer" in md and "done" in md
    assert "write_and_check" in md  # the tool call was surfaced
    clean = json.loads((run_dir / "clean_log.json").read_text())
    calls = [c for s in clean["steps"] for c in s["python_calls"]]
    assert any("write_and_check" in c for c in calls)


def test_transcript_roles(monkeypatch, tmp_path):
    stub = Settings(api_key=None, model_id="gpt-5.4-nano",
                    api_base="https://api.openai.com/v1", log_dir=tmp_path)
    monkeypatch.setattr(logs_module, "get_settings", lambda: stub)

    run_dir = logs_module.save_run(_agent(), "done", run_id="t-logtest")
    transcript = yaml.safe_load((run_dir / "transcript.yaml").read_text())
    roles = [m["role"] for m in transcript["messages"]]
    assert roles[0] == "system"
    assert "tool-response" in roles

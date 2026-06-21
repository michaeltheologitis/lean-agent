"""Tests for run logging (run.json + transcript.yaml), driven by a fake agent (no API)."""

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


class Role:
    def __init__(self, value):
        self.value = value


class Msg:
    def __init__(self, role, content):
        self.role = Role(role)
        self.content = content


class TaskStep:
    def __init__(self, task, messages):
        self.task = task
        self._messages = messages

    def to_messages(self):
        return self._messages


class ActionStep:
    def __init__(self, *, step_number, model_output, token_usage, messages):
        self.step_number = step_number
        self.model_output = model_output
        self.token_usage = token_usage
        self._messages = messages

    def to_messages(self):
        return self._messages


class Total:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens, self.total_tokens = i, o, i + o


class Monitor:
    def get_total_token_counts(self):
        return Total(100, 40)


class SystemPrompt:
    def to_messages(self):
        return [Msg("system", "you are a prover\nwith a multi-line\nsystem prompt")]


class Memory:
    def __init__(self, steps):
        self.steps = steps
        self.system_prompt = SystemPrompt()

    def get_full_steps(self):
        out = []
        for s in self.steps:
            if isinstance(s, TaskStep):
                out.append({"task": s.task})
            else:
                out.append({"step_number": s.step_number, "model_output": s.model_output,
                            "token_usage": {"input_tokens": s.token_usage.input_tokens,
                                            "output_tokens": s.token_usage.output_tokens}})
        return out


class FakeAgent:
    def __init__(self):
        self.memory = Memory([
            TaskStep("Prove smoke_true.", [Msg("user", "Prove smoke_true.")]),
            ActionStep(step_number=1, model_output="I'll fill it in.", token_usage=Usage(100, 40),
                       messages=[Msg("assistant", "calling tool"),
                                 Msg("tool-call", "lean_check(code='theorem smoke_true : True := by trivial')"),
                                 Msg("tool-response", "✓ valid")]),
        ])
        self.monitor = Monitor()


def _stub(monkeypatch, tmp_path):
    s = Settings(api_key=None, model_id="gpt-5.4-mini",
                 api_base="https://api.openai.com/v1", log_dir=tmp_path)
    monkeypatch.setattr(logs_module, "get_settings", lambda: s)


def test_save_run_writes_two_files(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path)
    run_dir = logs_module.save_run(FakeAgent(), "done", run_id="t-log",
                                   manifest={"benchmark": "smoke", "passed": True})
    assert run_dir.parent == tmp_path and run_dir.name.endswith("-t-log")
    assert {p.name for p in run_dir.iterdir()} == {"run.json", "transcript.yaml"}


def test_run_json_structure(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path)
    run_dir = logs_module.save_run(FakeAgent(), "done", run_id="t-log",
                                   manifest={"benchmark": "smoke"})
    data = json.loads((run_dir / "run.json").read_text())
    assert set(data) == {"manifest", "answer", "usage", "steps"}
    assert data["manifest"]["benchmark"] == "smoke"
    assert data["usage"] == {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}
    assert len(data["steps"]) == 2


def test_transcript_is_ordered_lineage(monkeypatch, tmp_path):
    _stub(monkeypatch, tmp_path)
    run_dir = logs_module.save_run(FakeAgent(), "done", run_id="t-log")
    t = yaml.safe_load((run_dir / "transcript.yaml").read_text())
    assert t["model_id"] == "gpt-5.4-mini"
    roles = [m["role"] for m in t["messages"]]
    assert roles[0] == "system"
    assert "user" in roles and "tool-call" in roles and "tool-response" in roles
    assert any("lean_check" in m["content"] for m in t["messages"])
    # readability: multi-line content renders as a real block (no escaped `\n`), and the
    # value round-trips intact when parsed back.
    raw = (run_dir / "transcript.yaml").read_text()
    assert "\\n" not in raw
    sys_content = next(m["content"] for m in t["messages"] if m["role"] == "system")
    assert sys_content == "you are a prover\nwith a multi-line\nsystem prompt"

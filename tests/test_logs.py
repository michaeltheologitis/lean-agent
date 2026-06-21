"""Tests for run logging, driven by a minimal fake agent (no API)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from lean_agent import logs as logs_module
from lean_agent.settings import Settings


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


class TaskStep:
    def __init__(self, task):
        self.task = task


class ActionStep:
    def __init__(self, *, step_number, model_output, code_action, observations, token_usage):
        self.step_number = step_number
        self.model_output = model_output
        self.code_action = code_action
        self.observations = observations
        self.token_usage = token_usage


class Total:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens, self.total_tokens = i, o, i + o


class Monitor:
    def get_total_token_counts(self):
        return Total(100, 40)


class Memory:
    def __init__(self, steps):
        self.steps = steps

    def get_full_steps(self):
        # smolagents returns serializable step dicts natively; emulate that.
        out = []
        for s in self.steps:
            if isinstance(s, TaskStep):
                out.append({"task": s.task})
            else:
                out.append({"step_number": s.step_number, "model_output": s.model_output,
                            "code_action": s.code_action, "observations": s.observations,
                            "token_usage": {"input_tokens": s.token_usage.input_tokens,
                                            "output_tokens": s.token_usage.output_tokens}})
        return out


class FakeAgent:
    def __init__(self):
        self.memory = Memory([
            TaskStep("Prove smoke_true."),
            ActionStep(step_number=1, model_output="I'll fill it in.",
                       code_action="write_and_check(file_path='x.lean', content='theorem t : True := by trivial')",
                       observations="status: compiled successfully", token_usage=Usage(100, 40)),
        ])
        self.monitor = Monitor()


def _stub_settings(monkeypatch, tmp_path):
    s = Settings(api_key=None, model_id="gpt-5.4-nano",
                 api_base="https://api.openai.com/v1", log_dir=tmp_path)
    monkeypatch.setattr(logs_module, "get_settings", lambda: s)


def test_save_run_writes_two_files(monkeypatch, tmp_path):
    _stub_settings(monkeypatch, tmp_path)
    run_dir = logs_module.save_run(FakeAgent(), "done", run_id="t-log",
                                   manifest={"benchmark": "smoke", "passed": True})
    assert run_dir.parent == tmp_path and run_dir.name.endswith("-t-log")
    assert {p.name for p in run_dir.iterdir()} == {"run.json", "run.md"}


def test_run_json_structure(monkeypatch, tmp_path):
    _stub_settings(monkeypatch, tmp_path)
    run_dir = logs_module.save_run(FakeAgent(), "done", run_id="t-log",
                                   manifest={"benchmark": "smoke"})
    data = json.loads((run_dir / "run.json").read_text())
    assert set(data) == {"manifest", "answer", "usage", "steps"}
    assert data["manifest"]["benchmark"] == "smoke"
    assert data["manifest"]["model_id"] == "gpt-5.4-nano"
    assert data["usage"] == {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}
    assert len(data["steps"]) == 2


def test_run_md_is_readable(monkeypatch, tmp_path):
    _stub_settings(monkeypatch, tmp_path)
    run_dir = logs_module.save_run(FakeAgent(), "done", run_id="t-log")
    md = (run_dir / "run.md").read_text()
    assert "## Task" in md and "Prove smoke_true." in md
    assert "write_and_check" in md          # the code it ran, from step.code_action
    assert "compiled successfully" in md    # the Lean output, from step.observations
    assert "## Final answer" in md and "done" in md

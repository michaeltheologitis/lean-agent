# lean-agent

A small [smolagents](https://github.com/huggingface/smolagents) `CodeAgent`
playground: a handful of example tools, typed settings, and per-run logs
saved as `{manifest, answer, logs}` JSON plus a readable YAML transcript.

**To get started: run the [Setup](#setup) steps below, then open [`playground.ipynb`](playground.ipynb).**

## Layout

```
src/lean_agent/
    settings.py     # Settings (model_id / api_key / api_base / log_dir)
                    # + create_logs / save_run / build_transcript
    tools.py        # 10 example @tool functions
tests/              # pytest suite (unit + one end-to-end test)
playground.ipynb    # demo: build agent, run a prompt, save logs
```

## Setup

```sh
uv sync
cp .env.example .env   # then open .env and paste your OpenAI API key
```

## Use

```python
from smolagents import CodeAgent, OpenAIServerModel
from lean_agent import get_settings, save_run
from lean_agent.tools import fibonacci, is_prime, temperature_convert

settings = get_settings()
agent = CodeAgent(
    tools=[fibonacci, is_prime, temperature_convert],
    model=OpenAIServerModel(
        model_id=settings.model_id,
        api_key=settings.api_key,
        api_base=settings.api_base,
    ),
    max_steps=6,
    instructions="Prefer using a tool when one fits the question. Be concise.",
)
answer = agent.run("Is 9973 prime?")
run_dir = save_run(agent, answer)    # or: save_run(agent, answer, run_id="my-experiment")
print(run_dir)
```

See `playground.ipynb` for the same workflow end-to-end.

## Tests

```sh
uv run pytest
```

The end-to-end test calls the model and is auto-skipped when no key is set.

## Logs

Each call to `save_run()` writes:

```
logs/<UTC-timestamp>-<run_id>/
    run.json         # {manifest, answer, logs: {total_usage, steps: [{usage, messages}, ...]}}
    transcript.yaml  # sanitized linear system / user / assistant / tool-* chat view
```

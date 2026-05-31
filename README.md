# lean-agent

This branch wires a small [smolagents](https://github.com/huggingface/smolagents)
`CodeAgent` to Lean through one deliberately narrow tool:
`lean_check_compiles`.

The repository includes a standalone Lean project in `lean_project/` that
depends on Mathlib. The example task asks the agent to replace a `sorry` in:

```text
lean_project/Problems/LeanWorkbookPlus2.lean
```

The test harness then writes the agent's candidate proof to an ignored scratch
file and validates it with `lake env lean`.

## Requirements

- Python 3.12
- `uv`
- Lean/Lake through `elan`
- a Token Factory API key

The default configured model is:

```dotenv
NEBIUS_MODEL_ID='deepseek-ai/DeepSeek-V3.2-fast'
NEBIUS_API_BASE='https://api.tokenfactory.nebius.com/v1/'
```

Token Factory did not list `deepseek-v4-flash` on this endpoint when checked.
It did list `deepseek-ai/DeepSeek-V4-Pro`; set `NEBIUS_MODEL_ID` to that if you
want to test the V4 model instead of the fast default.

## Setup

From the repository root:

```sh
uv sync
cp .env.example .env
```

Edit `.env` and add your key:

```dotenv
NEBIUS_API_KEY='...'
NEBIUS_MODEL_ID='deepseek-ai/DeepSeek-V3.2-fast'
NEBIUS_API_BASE='https://api.tokenfactory.nebius.com/v1/'
```

`TOKEN_FACTORY_API_KEY` is also accepted as an alias.

## Set Up The Lean Project

The Lean project is intentionally separate from the Python package:

```text
lean_project/
    lakefile.lean
    lake-manifest.json
    lean-toolchain
    Problems/LeanWorkbookPlus2.lean
```

Fetch Mathlib's compiled cache:

```sh
cd lean_project
lake exe cache get
lake env lean Problems/LeanWorkbookPlus2.lean
cd ..
```

The last command should succeed and print a warning that the declaration uses
`sorry`. That is expected; this file is the problem the agent will solve.

## Run The Agent Example

Run the model-backed test:

```sh
uv run pytest tests/test_lean_workbook_agent_e2e.py -q
```

That test:

1. reads `lean_project/Problems/LeanWorkbookPlus2.lean`;
2. asks the agent for a proof replacing the `sorry`;
3. rejects answers containing `sorry`, `admit`, or `axiom`;
4. writes the candidate to `lean_project/AgentOutput.lean`;
5. checks it with `lean_check_compiles`;
6. deletes `AgentOutput.lean` unless `KEEP_AGENT_LEAN_OUTPUT=1` is set.

To inspect the generated proof after a run:

```sh
KEEP_AGENT_LEAN_OUTPUT=1 uv run pytest tests/test_lean_workbook_agent_e2e.py -q
```

`lean_project/AgentOutput.lean` is ignored by Git.

## Playground

The notebook uses the same settings loader as the tests:

```sh
uv run jupyter lab playground.ipynb
```

Use it for manual experiments with `CodeAgent`, `OpenAIServerModel`, and
`LEAN_TOOLS`. For a reproducible smoke test, prefer the pytest command above.

## Test Without Spending Tokens

Blank the API key environment variables to force model-backed tests to skip:

```sh
NEBIUS_API_KEY= TOKEN_FACTORY_API_KEY= OPENAI_API_KEY= uv run pytest -q
```

This checks the deterministic unit tests and Lean tool plumbing without calling
the model API.

## Files That Should Not Be Committed

These are intentionally ignored:

- `.env`
- `.venv/`
- `logs/`
- `lean_project/.lake/`
- `lean_project/AgentOutput.lean`

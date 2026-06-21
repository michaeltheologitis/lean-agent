# lean-agent

A **common, inspectable baseline theorem-proving agent** for Lean 4 — one agent the team
runs, so results are comparable. The agent proves against a **pre-warmed Lean REPL
environment** (via [LeanInteract](https://github.com/augustepoiroux/LeanInteract)), which lets
us test the project's hypothesis: *is the agent more effective when concepts are given as
well-structured definitions/abstractions?*

## How it works

```
a problem .lean file
   │
   ├─ preamble  (imports + definitions/lemmas)  ──▶ pre-warm the Lean env (base environment)
   │                                            └─▶ pre-warm the LLM (appended to system prompt)
   └─ statement (the last `theorem ... := sorry`)  ──▶ the goal
                                   │
                                   ▼
   ToolCallingAgent ──tool──▶ lean_check(code)   # compile a candidate proof in the base env
                                   │             # → structured result: errors / remaining goal / valid
                                   ▼
   graded: a submission that is valid AND proves the target  →  logs/<run>/{run.json, transcript.yaml}
```

- **Pre-warmed environment.** A problem's `preamble` (everything above the goal — imports and
  any definitions/helper lemmas) is run **once** in the Lean REPL to build a base environment;
  every proof attempt runs *in* it, so the definitions are in scope. The same preamble is
  appended to the agent's system prompt. That's the "give Lean *and* the model the
  definitions" mechanism, and it's the knob the hypothesis turns.
- **One tool, `lean_check(code)`** ([lean.py](src/lean_agent/lean.py)). The agent submits a
  `theorem … := <proof>`; LeanInteract returns **structured** results — errors, `sorries`,
  goal states — so there's no regex for `sorry`, and the agent sees the remaining goal when a
  proof is incomplete.
- **A `ToolCallingAgent`, not a CodeAgent.** The model passes Lean as a string argument to the
  tool. (A CodeAgent makes it write Python, and it kept emitting bare Lean that the Python
  parser rejected.)
- **Logs are the product** ([logs.py](src/lean_agent/logs.py)). Each run writes `run.json` (the
  full structured record) and `transcript.yaml` — the top-down conversation lineage
  (system / user / assistant / tool-call / tool-response), the file you read to trace what
  happened. A batch also drops a `logs/<timestamp>-<label>-summary.jsonl`.

## Setup

```sh
uv sync
cp .env.example .env          # put your OPENAI_API_KEY in .env

# Lean toolchain (LeanInteract needs a default toolchain set):
curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y
export PATH="$HOME/.elan/bin:$PATH"
elan default leanprover/lean4:v4.29.1
```

The first agent run builds the Lean REPL (one-time, cached). Settings are **OpenAI-first**
(default `gpt-5.4-nano`); to use another OpenAI-compatible provider, leave `OPENAI_API_KEY`
empty and set `NEBIUS_*` / `TOKEN_FACTORY_*` (see [settings.py](src/lean_agent/settings.py)).

## Run the experiment (the hypothesis test)

An experiment is `benchmarks/data/experiments/<name>/` with one `.lean` file per **condition** —
same proposition, stated with vs. without the nice definitions. The last `theorem` in each file
is the goal; everything above it is pre-loaded. See
[even_self](benchmarks/data/experiments/even_self/) (a core-Lean example):

```sh
uv run python run.py --experiment even_self
```

It runs each condition with the same agent and prints a comparison; read each
`logs/<run-folder>/transcript.yaml` to see *why* one condition did better. To make your own:
drop a `benchmarks/data/experiments/<name>/` dir with a `.lean` file per condition. For a real
(Mathlib) study, set `LEAN_PROJECT` to a **built** Mathlib project. There's also a
[`notebooks/showcase.ipynb`](notebooks/showcase.ipynb) walkthrough.

## Run a benchmark

```sh
uv run pytest -q                       # unit tests (no API, no Lean)
uv run python run.py --benchmark smoke # core Lean (no Mathlib) — works anywhere

# minif2f / putnam need a built Mathlib project at the matching version:
git clone https://github.com/yangky11/miniF2F-lean4 && (cd miniF2F-lean4 && lake exe cache get)
uv run python run.py --benchmark minif2f --n 5
```

`smoke`/`minif2f`/`putnam` load from `benchmarks/data/<name>/` (see each `SOURCE.md`).

## Layout

```
src/lean_agent/        # the core agent library
  settings.py          # OpenAI-first config + Lean version/project
  problem.py           # Problem (preamble + statement)
  lean.py              # LeanInteract backend: Lean (server + base env), lean_check tool
  agent.py             # solve() — pre-warm env + prompt, run agent, grade, log
  logs.py              # run.json + transcript.yaml
benchmarks/            # the evaluation harness (kept out of the core library)
  __init__.py          # load / load_experiment (the .lean → Problem split)
  data/
    experiments/<name>/      # hypothesis conditions (one .lean per condition)
    {smoke,minif2f,putnam}/  # vendored benchmark statements
run.py                 # the CLI (--benchmark / --experiment)
notebooks/showcase.ipynb
tests/                 # unit tests (no API/Lean)
```

## Not committed

`.env`, `logs/`, the Mathlib checkouts (`PutnamBench/`, `miniF2F-lean4/`), and
`.lake/` build dirs are gitignored.

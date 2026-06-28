# lean-agent

A common, inspectable baseline theorem-proving agent for Lean 4 — one agent the team runs, so
results are comparable. It proves against a **pre-warmed Lean REPL environment** (via
[LeanInteract](https://github.com/augustepoiroux/LeanInteract)) to test the project's
hypothesis: *is the agent more effective when concepts are given as well-structured
definitions?*

> **Start here:** [`notebooks/showcase.ipynb`](notebooks/showcase.ipynb) builds the whole thing
> up step by step — define a concept → prove against it → run the agent → the
> with-vs-without-definitions experiment.

## How it works

A problem is a `.lean` file split at its last `theorem`: everything above is the **preamble**
(imports + definitions), the theorem is the **goal**. The preamble is loaded once into a Lean
REPL *and* into the model's system prompt; a `ToolCallingAgent` then iterates with one tool,
`lean_check(code)`, which compiles candidates and returns structured errors / remaining goals.
Each run is graded (a real, complete proof of the goal) and logged to `logs/<run>/` —
`run.json`, `transcript.yaml`, and on success a self-contained, re-compilable `proof.lean`
(preamble + the winning proof). Two handles on the run: `solve(...)` returns the proof in
`result["proof"]`, and `extra_instructions="…"` (CLI: `--extra-instruct "…"`) appends your own
guidance to the agent's system prompt — empty by default. The notebook's section 6 shows both.

## Setup

```sh
uv sync
cp .env.example .env          # put your OPENAI_API_KEY in .env

# Lean (LeanInteract needs a default toolchain):
curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y
elan default leanprover/lean4:v4.29.1
```

Default model is OpenAI `gpt-5.4-mini` (override via env — see
[settings.py](src/lean_agent/settings.py)). The first run builds the Lean REPL (one-time).

**Other providers (OpenAI-compatible).** The agent talks to any OpenAI-compatible endpoint, so
you can swap OpenAI for Token Factory / Nebius / a local vLLM by setting env vars. Resolution is
OpenAI-first, so leave `OPENAI_API_KEY` unset for the dedicated slot to win. E.g. Token Factory
running a DeepSeek model:

```sh
TOKEN_FACTORY_API_KEY=...                                   # your key
TOKEN_FACTORY_MODEL=deepseek-ai/DeepSeek-V4-Pro             # any tool-calling model in the catalog
TOKEN_FACTORY_BASE_URL=https://api.tokenfactory.nebius.com/v1/
```

## Run it

```sh
uv run pytest -q                              # unit tests (no API, no Lean)
uv run python run.py --benchmark smoke        # core-Lean plumbing check
```

`minif2f` / `putnam` need a built Mathlib project — clone the source repo (e.g.
`git clone https://github.com/yangky11/miniF2F-lean4 && cd miniF2F-lean4 && lake exe cache get`)
or set `LEAN_PROJECT`, then `--benchmark minif2f`.

**Benchmarks vs. experiments.** Benchmarks (`smoke` / `minif2f` / `putnam`) are vendored `.lean`
files loaded by `load(...)`. For your own problems or a notation experiment, build a `Problem(...)`
in Python — the `preamble` holds any definitions/lemmas, the `statement` is the goal — and pass it
to `solve(...)`. The notebook (section 5) does exactly that. There's no file-based experiment loader.

## Layout

```
src/lean_agent/   # core library: settings, problem, lean (LeanInteract), agent, logs
benchmarks/       # eval harness (out of the core): load() + data/
run.py            # CLI (--benchmark)
notebooks/        # showcase.ipynb
```

`.env`, `logs/`, and the Mathlib checkouts (`PutnamBench/`, `miniF2F-lean4/`) are gitignored.

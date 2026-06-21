# lean-agent

A **common, inspectable baseline theorem-proving agent** for Lean 4 — one agent the whole
team runs, so results are comparable. It wires a [smolagents](https://github.com/huggingface/smolagents)
`CodeAgent` to Lean through a small tool surface, runs it over a benchmark, and logs
everything so you can see exactly what the model saw and did.

The goal of this milestone is the **harness**, not a high proof rate: a single agent
everyone can run and compare, with complete logs. A fully-logged failure is a useful result.

## How it works

```
model (OpenAI gpt-5.4-nano)
   │
   ▼
build_agent ──tools──▶ write_and_check(content)   # write the whole file + compile, return Lean output
   │
   ▼
solve(problem) ──▶ agent iterates on the compiler output ──▶ candidate .lean file
   │
   ▼
grade ──▶ compiles AND no sorry/admit            (+ advisory statement_changed flag)
   │
   ▼
logs/<run>/{run.json, transcript.yaml, clean_log.json, clean_log.md}
```

- **One agent** (`lean_agent.agent`): `build_agent()` + `solve()`. Parameterized, not forked.
- **Lean tools** (`lean_agent.lean`): `lean_check_compiles` and the agent's editing loop
  `write_and_check`. A file with `sorry` compiles with only a *warning* (exit 0) — the tool
  flags that explicitly so a complete-looking compile isn't mistaken for a solved problem.
- **Benchmarks** (`lean_agent.benchmarks`): decoupled adapters over one shared `Problem`
  mechanic — `smoke` (core Lean, no Mathlib), `putnam`, `minif2f`. Statements are vendored
  under `data/`; the harness grades by compiling them in a Lean project.
- **Logs are the product** (`lean_agent.logs`): every run writes the raw record
  (`run.json`, `transcript.yaml`) and a readable per-step distillation (`clean_log.md`).

## Requirements

- Python 3.12 + [`uv`](https://docs.astral.sh/uv/)
- An OpenAI API key (`OPENAI_API_KEY`) for `gpt-5.4-nano`
- Lean via [`elan`](https://github.com/leanprover/elan) — only needed to actually compile

## Setup

```sh
uv sync
cp .env.example .env      # then put your OPENAI_API_KEY in .env
```

Settings are **OpenAI-first** (default model `gpt-5.4-nano`). To use another
OpenAI-compatible provider, leave `OPENAI_API_KEY` empty and set `NEBIUS_*` /
`TOKEN_FACTORY_*` instead (see `src/lean_agent/settings.py`).

## Run it

**Unit tests** (no API, no Lean — always run):

```sh
uv run pytest -q
```

**Live end-to-end** with `gpt-5.4-nano` on the `smoke` benchmark (core Lean, no Mathlib).
Install a Lean toolchain first, then:

```sh
curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y   # one-time
export PATH="$HOME/.elan/bin:$PATH"
uv run python scripts/run.py --benchmark smoke --max-steps 4
```

This is the fast plumbing check — it confirms the model ↔ Lean ↔ logs loop works without a
multi-GB Mathlib build. Then read `logs/<run-folder>/clean_log.md`.

**Real benchmarks** (`putnam`, `minif2f`) need a built Mathlib project at the matching
version. Each benchmark defaults to a gitignored sibling checkout of its own source repo:

```sh
# MiniF2F (Mathlib v4.24.0) — the right benchmark for weak models (easy problems)
git clone https://github.com/yangky11/miniF2F-lean4
cd miniF2F-lean4 && lake exe cache get && cd -
uv run python scripts/run.py --benchmark minif2f --n 5

# PutnamBench (Mathlib v4.27.0) — hard; expect low pass rates with a small model
git clone https://github.com/trishullab/PutnamBench
cd PutnamBench/lean4 && lake exe cache get && cd -
uv run python scripts/run.py --benchmark putnam --n 5
```

Override the project with `--project /path/to/lean-project`. See `data/<name>/SOURCE.md` for
provenance and exact versions.

## Layout

```
src/lean_agent/
  settings.py            # OpenAI-first config
  agent.py               # build_agent + solve — the shared agent
  lean.py                # lean_check_compiles + write_and_check
  logs.py                # run.json / transcript.yaml / clean_log.{json,md}
  benchmarks/{putnam,minif2f,smoke}.py
data/{putnam,minif2f,smoke}/   # vendored statements (+ SOURCE.md)
lean_project_core/             # tiny core-only Lean project for smoke
scripts/run.py                 # the CLI
tests/                         # unit tests (no API/Lean)
```

## Not committed

`.env`, `logs/`, `results/`, the sibling benchmark checkouts (`PutnamBench/`,
`miniF2F-lean4/`), and the `.lake/` build dirs are gitignored.

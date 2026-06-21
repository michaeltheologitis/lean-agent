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
solve(problem) ──tool──▶ write_and_check(file_path, content)  # write the file + compile, return Lean output
   │
   ▼
agent iterates on the compiler output ──▶ candidate .lean file
   │
   ▼
grade ──▶ compiles AND no sorry/admit            (+ advisory statement_changed flag)
   │
   ▼
logs/<run>/{run.json, run.md}
```

- **One agent** (`lean_agent.agent`): `solve(problem)` builds the model + a smolagents
  `CodeAgent`, runs it, grades, logs. Parameterized, not forked.
- **Lean tools** (`lean_agent.tools`): `write_and_check(file_path, content)` — the agent's
  editing loop — plus the `compile_file` / `has_sorry` helpers the grader reuses. Checking
  compilation means running the Lean compiler (`lake env lean`); there's no substitute. A
  file with `sorry` compiles with only a *warning* (exit 0), so the tool flags that explicitly
  instead of reporting a clean success.
- **Benchmarks** (`lean_agent.benchmarks`): one `Problem` + one `load(benchmark)` over the
  vendored statements in `data/` — `smoke` (core Lean, no Mathlib), `putnam`, `minif2f`.
- **Logs are the product** (`lean_agent.logs`): every run writes `run.json` (the full
  structured record, straight from smolagents) and `run.md` (a readable per-step view — what
  the model thought, the code it ran, the Lean output, token usage).

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
uv run python run.py --benchmark smoke
```

This is the fast plumbing check — it confirms the model ↔ Lean ↔ logs loop works without a
multi-GB Mathlib build. Then read `logs/<run-folder>/run.md`.

**Real benchmarks** (`putnam`, `minif2f`) need a built Mathlib project at the matching
version. Each benchmark defaults to a gitignored sibling checkout of its own source repo:

```sh
# MiniF2F (Mathlib v4.24.0) — the right benchmark for weak models (easy problems)
git clone https://github.com/yangky11/miniF2F-lean4
cd miniF2F-lean4 && lake exe cache get && cd -
uv run python run.py --benchmark minif2f --n 5

# PutnamBench (Mathlib v4.27.0) — hard; expect low pass rates with a small model
git clone https://github.com/trishullab/PutnamBench
cd PutnamBench/lean4 && lake exe cache get && cd -
uv run python run.py --benchmark putnam --n 5
```

Override the project with `--project /path/to/lean-project`. See `data/<name>/SOURCE.md` for
provenance and exact versions.

## Layout

```
src/lean_agent/
  settings.py      # OpenAI-first config
  tools.py         # write_and_check / compile_file / has_sorry
  agent.py         # solve() — the shared agent
  benchmarks.py    # Problem + load(benchmark)
  logs.py          # run.json + run.md
run.py             # the CLI
data/{putnam,minif2f,smoke}/   # vendored statements (+ SOURCE.md)
lean_project_core/             # tiny core-only Lean project for smoke
tests/                         # unit tests (no API/Lean)
```

## Not committed

`.env`, `logs/`, `results/`, the sibling benchmark checkouts (`PutnamBench/`,
`miniF2F-lean4/`), and the `.lake/` build dirs are gitignored.

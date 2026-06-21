# Baseline harness — what changed and what we saw

_For Michael + Dean. Covers the consolidation of the team's June-18 work into one runnable
baseline agent on `main`._

## TL;DR

The team's contributions were merged to `main` and refactored into **one agent everyone can
run**, with two benchmarks wired in (PutnamBench + MiniF2F) and complete logging. The full
loop — model → Lean tools → compile → grade → logs — was **live-tested with `gpt-5.4-nano`**
and works end-to-end (3/3 on a trivial core-Lean set). Along the way we found and fixed the
exact "`sorry` looks like success" bug the team flagged. Real Putnam/MiniF2F grading needs a
built Mathlib project (a one-time clone + `lake exe cache get` per machine); that step is
documented but wasn't run here because this box has no Mathlib build.

## What the milestone asked vs. what existed

The June-18 write-up credited three contributions. Checking the merged branch:

- **Naren — clean logs:** real and integrated. ✅
- **Nhan — PutnamBench:** 672 statements were in-repo; his `putnambench_tools.py` was on a
  separate branch and was a *sketch* (imported modules that didn't exist). Intent folded in. ⚠️→✅
- **Evan — "advanced Lean tools (premise/lemma/identifier search)":** **not in the code on
  any branch.** The agent only ever had compile-check + `lean_goal` (the latter from the
  external `lean-lsp-mcp`). The "curated set" describes lean-lsp-mcp's *capabilities*, not
  tools wired into the agent. Flagged as the top open item (see Next steps). ❌

Also: the eval was run on **DeepSeek-V3.2**, not the OpenAI model the milestone specified.
And there was **no single importable agent** — two divergent scripts each defined their own
`write_and_check`, one with a hardcoded `/home/aurasl/...` Linux path.

## What was done

**One agent, deliberately small layout** (~530 lines of Python in `src/lean_agent/` + `run.py`):
- `agent.py` — `solve(problem)`: builds the model + a smolagents `CodeAgent`, runs it, grades,
  logs. Killed the two duplicated `write_and_check` copies.
- `tools.py` — plain `@tool` functions: `write_and_check(file_path, content)` (finds the Lean
  project by walking up to `lean-toolchain`) + the `compile_file` / `has_sorry` helpers the
  grader reuses.
- `logs.py` — uses smolagents' **native** step data (`step.code_action` / `.observations` /
  `agent.memory.get_full_steps()`); two files per run (`run.json` + readable `run.md`).
- `settings.py` — **OpenAI-first** (default `gpt-5.4-nano`). Fixed a latent bug where an
  OpenAI key paired with a DeepSeek model id + Nebius base.
- `benchmarks.py` — one `Problem` + one `load(benchmark)`. No registry/framework.
- `run.py` — one CLI: run the agent over `--benchmark X --n K`, log everything, write a
  results JSONL.

> Note: the first cut was over-built (a logging module that re-parsed tool calls with
> AST/regex, a `make_write_and_check` factory, four files per run, `build_model`/`build_agent`/
> `solve`/`RunResult` layering, all 672 Putnam files). A second pass cut it ~in half with no
> behavior change — the numbers below still hold.

**Benchmarks wired in:**
- **PutnamBench** — small curated subset of proof-only statements (the full set comes with the
  PutnamBench checkout you clone to grade). Parsing descends from Nhan's loader.
- **MiniF2F** — newly imported (Evan's suggestion; it has the *easy* problems a weak model
  can actually land). 18-problem curated subset from `yangky11/miniF2F-lean4`.
- **smoke** — 3 trivial core-Lean goals (no Mathlib) so the harness is live-testable anywhere
  with just a Lean toolchain.

**Removed as unrelated/broken:** the 10 toy tools (`fibonacci`, `caesar_cipher`, …), the
toy-tool notebook, the two hardcoded-path experiments, a one-off migration script, stale
docs. Tests rewritten: **28 unit tests, no API/Lean needed**, covering settings, the Lean
tools (incl. the sorry flag), the benchmark loaders + grader, and the full logging path.

## What we tested and saw (live, `gpt-5.4-nano`)

Ran `run.py --benchmark smoke` against the real OpenAI API with a real Lean v4.29.1
toolchain. **3/3 solved.** The clean logs show the model reasoning correctly and driving the
tools — e.g. for `a + b = b + a`:

> Thought: I'll prove `a + b = b + a` for naturals using `Nat.add_comm` … →
> `write_and_check("… := by simpa using Nat.add_comm a b")` → `status: compiled successfully`
> → `final_answer("done")`.

Token cost was tiny (≈5–8k input, ≈170–380 output per problem). This proves the *harness*,
not proving ability — but that was the milestone: a loop you can run and inspect.

**Bug found + fixed (the team's `sorry` trap).** Lean emits `` declaration uses `sorry` ``
with **backticks** as a *warning* (exit code 0), so a `sorry` file reads as a clean compile.
The compile tool now detects this and reports `compiled WITH sorry/admit (INCOMPLETE)`;
verified live. The grader is independently safe (it rejects `sorry`/`admit` in the text
before compiling).

## What is NOT verified here

- **Real Putnam/MiniF2F grades.** Those need a built Mathlib project at the matching version
  (Putnam v4.27.0, MiniF2F v4.24.0). This box has no Mathlib build (multi-GB). The flow is
  documented (`README.md`, `data/*/SOURCE.md`): clone the source repo as a sibling, `lake exe
  cache get`, run. The vendored statements come from those repos, so versions match.
- **Whether the model solves anything non-trivial.** Expected to be ~0 on Putnam with a small
  model; MiniF2F is where we'll get real signal.

## The experiment harness (the hypothesis test — now built)

We integrated **[LeanInteract](https://github.com/augustepoiroux/LeanInteract)** (a Python
wrapper over the Lean REPL) as the Lean backend, because it gives **persistent environments** —
exactly what the hypothesis needs. The agent no longer compiles whole files via a subprocess;
it proves against a **pre-warmed environment**:

- A problem's **preamble** (imports + definitions/lemmas) is run once to build a base
  environment; every proof attempt runs *in* it. The same preamble is appended to the model's
  **system prompt**. So a single definition block pre-warms *both* Lean and the LLM — the knob
  the hypothesis turns.
- An **experiment** is `data/experiments/<name>/` with one `.lean` file per **condition**
  (e.g. `notated.lean` vs `raw.lean`). `run.py --experiment <name>` runs each condition with
  the same agent and compares. Making one is just dropping two files — no code.
- Grading is **structured** (LeanInteract returns errors/`sorries`/goals), so the regex
  `sorry` check is gone, and the agent sees the *remaining goal* when a proof is incomplete.
- We switched `CodeAgent → ToolCallingAgent`: with a CodeAgent the model writes Python and kept
  emitting bare Lean that the Python parser rejected (one run spiralled for 7 steps fighting a
  phantom "unicode" error). Tool calls pass Lean as a string — that failure class is gone.

**Live, end-to-end:** the example `even_self` experiment runs on this machine (core Lean, no
Mathlib) — gpt-5.4-nano solves both conditions, the raw (no-definitions) condition taking more
steps. This proves the machinery; the real study needs Mathlib definitions + a built project.

## Next steps (concrete)

1. **Author the real experiment(s)** from the book tasks: for each, a `notated.lean` (using the
   book's definitions/abstractions) and a `raw.lean` (desugared), both compiling against a
   built Mathlib project (`LEAN_PROJECT`). Run `--experiment <name>`, then **deep-dive the
   `run.md`s**: where does the raw condition get stuck that the notated one doesn't?
2. **Run a MiniF2F baseline** on a Mathlib machine (`--benchmark minif2f --n 10..20`) for a
   reference number + inspectable failures.
3. **More "correct" Lean tools** (optional, behind the same tool seam): LeanInteract's tactic
   mode gives goal states step-by-step; `lean-lsp-mcp` adds premise/lemma search
   (`leansearch`, `loogle`). Add and compare with/without.

## How to run it

See `README.md`. Shortest path: `uv run pytest -q`, then set up `elan` (incl. `elan default
…`) and `uv run python run.py --experiment even_self`, then read a `run.md`.

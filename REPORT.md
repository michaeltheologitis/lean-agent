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

**One agent, clean layout** (`src/lean_agent/`):
- `agent.py` — the single shared `CodeAgent`: `build_agent()` + `solve()`. Killed the two
  duplicated `write_and_check` copies.
- `lean.py` — the Lean tool surface: `lean_check_compiles` + `make_write_and_check`.
- `logs.py` — unified persistence: raw `run.json`/`transcript.yaml` + Naren's
  `clean_log.json`/`.md`.
- `settings.py` — **OpenAI-first** (default `gpt-5.4-nano`). Fixed a latent bug where an
  OpenAI key paired with a DeepSeek model id + Nebius base.
- `benchmarks/{putnam,minif2f,smoke}.py` — decoupled adapters over one shared `Problem`
  (load → prompt → grade). No registry/framework.
- `scripts/run.py` — one CLI: run the agent over `--benchmark X --n K`, log everything,
  write a results JSONL.

**Benchmarks wired in:**
- **PutnamBench** — 672 vendored statements (proof-only by default; answer-proof problems are
  ill-posed once the ground-truth answer is stripped). Folds in Nhan's loader.
- **MiniF2F** — newly imported (Evan's suggestion; it has the *easy* problems a weak model
  can actually land). 18-problem curated subset vendored from `yangky11/miniF2F-lean4`.
- **smoke** — 3 trivial core-Lean goals (no Mathlib) so the harness is live-testable anywhere
  with just a Lean toolchain.

**Removed as unrelated/broken:** the 10 toy tools (`fibonacci`, `caesar_cipher`, …), the
toy-tool notebook, the two hardcoded-path experiments, a one-off migration script, stale
docs. Tests rewritten: **28 unit tests, no API/Lean needed**, covering settings, the Lean
tools (incl. the sorry flag), the benchmark loaders + grader, and the full logging path.

## What we tested and saw (live, `gpt-5.4-nano`)

Ran `scripts/run.py --benchmark smoke` against the real OpenAI API with a real Lean v4.29.1
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

## Next steps (concrete)

1. **Run the MiniF2F baseline on a Mathlib machine.** Clone + cache `miniF2F-lean4`, run
   `--benchmark minif2f --n 10..20`. This gives the first real number on `gpt-5.4-nano` and a
   set of inspectable failures to deep-dive.
2. **Wire the advanced Lean tools into the agent** (the missing Evan piece). `lean-lsp-mcp`
   already exposes premise/lemma search (`leansearch`, `loogle`, `lean_goal`); the agent
   currently gets none of them. Add them behind a flag and compare with/without.
3. **`lean_goal` (proof state)** as a `--sighted` option — it worked in the old script; just
   isn't in the baseline yet (kept the baseline dependency-light).
4. **For the ~June-25 notation hypothesis:** the harness is ready — point a benchmark adapter
   at the book's tasks in two conditions (raw vs. notated) and compare logs. The old
   `notation_pilot.py` (removed; in git history on `gcd-lean-tools-extra`) is a reusable
   template for the two-condition design.

## How to run it

See `README.md`. Shortest path to see it work: `uv run pytest -q`, then install `elan` and
`uv run python scripts/run.py --benchmark smoke`, then read a `clean_log.md`.

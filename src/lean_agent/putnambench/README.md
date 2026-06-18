# PutnamBench proof-agent benchmark tools

Three modules to turn the [PutnamBench](https://github.com/trishullab/PutnamBench)
Lean4 problems into a benchmark for a proof-writing agent.

- `putnam_loader.py` — parse the 672 `.lean` problems into structured `Problem`
  objects, joined with tags/informal text from `informal/putnam.json`.
- `verify.py` — compile a candidate proof with the project's Lean + Mathlib and
  return pass/fail. The compiler is the grader.
- `harness.py` — run an agent over a problem set with pass@k and an optional
  compiler-feedback repair loop; stream results to JSONL; aggregate scores.

## One-time setup (the heavy part)

Verification needs a *built* Lean project, not just the source files.

```bash
git clone --depth 1 https://github.com/trishullab/PutnamBench.git
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
cd PutnamBench/lean4
lake exe cache get      # pulls prebuilt Mathlib; skip this and you compile it from source
lake build
```

`lake exe cache get` is the step that saves hours. The repo pins
`leanprover/lean4:v4.27.0`; elan reads `lean-toolchain` and installs it, so don't
override it.

If you only want to read statements (no compilation), you can skip elan/lake and
just use the loader.

## Two task types

About 426 problems are proof-only (one `sorry` in the theorem). The other 246 are
answer-extraction: an `abbrev ..._solution := sorry` whose ground truth lives in a
`-- comment`. The loader recovers that ground truth for all 246. By default the
benchmark fills it in so your agent is judged purely on proving the theorem. Set
`fill_answers=False` only if your agent should also produce the answer.

## Usage

```python
from putnam_loader import load_problems
from harness import run_benchmark, score_report

# 1. Load a slice (filter by tag, year, type, or name)
problems = load_problems("PutnamBench", tags=["number_theory"], years=(2000, 2025))

# 2. Wrap your HF agent as a callable returning the proof body (what replaces `sorry`)
def agent(problem, feedback=None):
    prompt = problem.statement_for_agent()      # statement ending in sorry
    # feedback is the previous Lean error when repair_rounds > 0
    return my_hf_agent.generate(prompt, error=feedback)   # e.g. "by\n  norm_num"

# 3. Run. pass@k for stochastic agents; repair_rounds feeds Lean errors back.
run_benchmark(
    agent, "PutnamBench",
    out_path="results.jsonl",
    tags=["number_theory"],
    k=3,
    repair_rounds=2,
    timeout=300,
)

# 4. Aggregate
print(score_report("results.jsonl"))
```

The proof string is whatever follows `:=`, so return either a `by ...` tactic
block or a term. The harness assembles the full file, compiles it, and a problem
counts as solved only if Lean exits clean with no `error:` and no `sorry`/`sorryAx`
in the output. `sorry`/`admit` in the submitted proof are rejected as cheats
before compilation.

## Notes

- Each compile imports all of Mathlib. The first few are slow while oleans load;
  a 300s timeout per attempt is a reasonable default.
- `run_benchmark` resumes by default: it skips problems already in `results.jsonl`.
  Delete the file or pass `resume=False` to start fresh.
- `Problem.build_file(proof)` gives you the exact source that gets compiled if you
  want to debug a single case by hand.

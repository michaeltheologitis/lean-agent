# PutnamBench (vendored statements)

These `.lean` files are the **PutnamBench** problem statements, extracted with the
ground-truth answers stripped, so each is a `sorry`-stub the agent fills in.

- **Source:** PutnamBench (https://github.com/trishullab/PutnamBench), Lean 4 split
- **Lean / Mathlib:** authored against PutnamBench's Lean project, **Mathlib v4.27.0**
- **Extraction:** PutnamBench's own loader enumerated the problems; the ground-truth answer
  comment after each `..._solution := sorry` was removed (the proof — and any answer def —
  stays `sorry`). Years 1962–2025, 672 problems.

Two task types (see `benchmarks/putnam.py`):
- **proof** — fill the single theorem `sorry`.
- **answer_proof** — also has `abbrev ..._solution := sorry`; the closed-form answer was
  stripped, so the agent would have to *guess* it. `putnam.load()` defaults to proof-only.

**Grading:** clone PutnamBench as a sibling and build its Lean project, then run the agent:

```sh
git clone https://github.com/trishullab/PutnamBench    # next to this repo, gitignored
cd PutnamBench/lean4 && lake exe cache get && cd -
uv run python scripts/run.py --benchmark putnam --n 5  # defaults --project to ../PutnamBench/lean4
```

The vendored statements were extracted from PutnamBench, so they compile at its Mathlib
(v4.27.0).

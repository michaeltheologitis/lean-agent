# PutnamBench (vendored statements)

These `.lean` files are the **PutnamBench** problem statements, extracted with the
ground-truth answers stripped, so each is a `sorry`-stub the agent fills in.

- **Source:** PutnamBench (https://github.com/trishullab/PutnamBench), Lean 4 split
- **Lean / Mathlib:** authored against PutnamBench's Lean project, **Mathlib v4.27.0**
- **Subset:** just **3 example** proof-only problems (no `..._solution` def to guess), spanning
  1962–2013 — enough to see the shape. The full 672-problem set comes with the PutnamBench
  checkout you clone to grade (below), so we don't vendor more.
- **Extraction:** PutnamBench's own loader enumerated the problems; the ground-truth answer
  comment after each `..._solution := sorry` was removed.

**Grading:** clone PutnamBench as a sibling and build its Lean project, then run the agent:

```sh
git clone https://github.com/trishullab/PutnamBench    # next to this repo, gitignored
cd PutnamBench/lean4 && lake exe cache get && cd -
uv run python run.py --benchmark putnam --n 5  # defaults --project to ../PutnamBench/lean4
```

The vendored statements were extracted from PutnamBench, so they compile at its Mathlib
(v4.27.0).

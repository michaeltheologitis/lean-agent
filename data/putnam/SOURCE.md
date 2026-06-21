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

**Grading caveat:** to grade these you need a built Lean project at the matching Mathlib
version (v4.27.0). The repo's `lean_project/` is a different pin — point `--project` at a
v4.27.0 project before trusting grades.

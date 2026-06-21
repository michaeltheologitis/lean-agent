# MiniF2F (vendored subset)

These `.lean` files are a small curated subset of the **MiniF2F** benchmark, copied verbatim
for provenance.

- **Source:** https://github.com/yangky11/miniF2F-lean4 (commit `5746b7d`)
- **Split:** `MiniF2F/Valid/` (the dev split; `Test/` is held out and intentionally not
  vendored)
- **Lean / Mathlib:** `leanprover/lean4:v4.24.0`, Mathlib `v4.24.0`
- **Subset:** a deterministic slice — first 8 `mathd_algebra_*`, 6 `mathd_numbertheory_*`,
  2 `induction_*`, 2 `amc12a_*` (sorted by name). Easy→medium, chosen so a weak model has a
  real chance on some. Regenerate/extend with `scripts/import_minif2f.py` (or re-copy from the
  source repo).

Each file is self-contained (`import Mathlib`, `set_option maxHeartbeats 0`, an `open`, one
`theorem ... := by sorry`).

**Grading caveat:** to grade these you need a built Lean project at the matching Mathlib
version (v4.24.0). The repo's `lean_project/` is a different pin — point `--project` at a
v4.24.0 project before trusting grades.

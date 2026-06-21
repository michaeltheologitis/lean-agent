# MiniF2F (vendored subset)

These `.lean` files are a small curated subset of the **MiniF2F** benchmark, copied verbatim
for provenance.

- **Source:** https://github.com/yangky11/miniF2F-lean4 (commit `5746b7d`)
- **Split:** `MiniF2F/Valid/` (the dev split; `Test/` is held out and intentionally not
  vendored)
- **Lean / Mathlib:** `leanprover/lean4:v4.24.0`, Mathlib `v4.24.0`
- **Subset:** just **3 example** problems (`mathd_algebra_10`, `mathd_algebra_116`,
  `mathd_numbertheory_101`) — enough to see the shape. Copy more from the source repo's
  `MiniF2F/Valid/` into this folder if you want a bigger run.

Each file is self-contained (`import Mathlib`, `set_option maxHeartbeats 0`, an `open`, one
`theorem ... := by sorry`).

**Grading:** clone the source repo as a sibling and build it, then run the agent against it:

```sh
git clone https://github.com/yangky11/miniF2F-lean4    # next to this repo, gitignored
cd miniF2F-lean4 && lake exe cache get && cd -
uv run python run.py --benchmark minif2f --n 5  # defaults --project to ../miniF2F-lean4
```

The vendored statements came from that repo, so they compile at its Mathlib (v4.24.0).

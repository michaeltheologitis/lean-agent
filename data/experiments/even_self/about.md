# Experiment: even_self

A tiny, **core-Lean** (no Mathlib) example of the hypothesis test — does giving the agent
well-structured definitions/lemmas make it more effective?

Same proposition, two conditions (one `.lean` file each; the **last** `theorem` is the goal,
everything above it is pre-loaded into the environment + the system prompt):

- **notated.lean** — defines `IsEven` and hands the agent the lemma `isEven_add_self`. The
  goal `IsEven (n + n)` is then one step (`exact isEven_add_self n`).
- **raw.lean** — the desugared goal `∃ k, n + n = 2 * k`, no helpers. The agent must produce
  the witness and the arithmetic (`⟨n, by omega⟩`).

Run both and compare:

```sh
uv run python run.py --experiment even_self
```

To make your own experiment: drop a `data/experiments/<name>/` dir with one `.lean` file per
condition. Use real definitions/lemmas (with Mathlib) for the actual study — set `LEAN_PROJECT`
to a built Mathlib project so the conditions compile against it.

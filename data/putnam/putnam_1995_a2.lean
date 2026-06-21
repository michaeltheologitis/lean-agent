import Mathlib

open Filter Topology Real

abbrev putnam_1995_a2_solution : Set (ℝ × ℝ) := sorry
/--
For what pairs $(a,b)$ of positive real numbers does the improper integral \[ \int_{b}^{\infty} \left( \sqrt{\sqrt{x+a}-\sqrt{x}} - \sqrt{\sqrt{x}-\sqrt{x-b}} \right)\,dx \] converge?
-/
theorem putnam_1995_a2
(habconv : (ℝ × ℝ) → Prop)
(habconv_def : habconv = fun ⟨a,b⟩ =>
∃ limit : ℝ, Tendsto (fun t : ℝ => ∫ x in (Set.Icc b t), (sqrt (sqrt (x + a) - sqrt x) - sqrt (sqrt x - sqrt (x - b)))) atTop (𝓝 limit))
: ∀ ab : ℝ × ℝ, ab.1 > 0 ∧ ab.2 > 0 → (habconv ab ↔ ab ∈ putnam_1995_a2_solution) :=
sorry

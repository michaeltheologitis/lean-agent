import Mathlib

open Topology Filter Nat

noncomputable abbrev putnam_2014_a3_solution : ℝ := sorry
/--
Let \( a_0 = \frac{5}{2} \) and \( a_k = a_{k-1}^2 - 2 \) for \( k \geq 1 \). Compute \( \prod_{k=0}^{\infty} \left(1 - \frac{1}{a_k}\right) \) in closed form.
-/
theorem putnam_2014_a3
(a : ℕ → ℝ)
(a0 : a 0 = 5 / 2)
(ak : ∀ k ≥ 1, a k = (a (k - 1)) ^ 2 - 2)
: Tendsto (fun n : ℕ => ∏ k ∈ Finset.range n, (1 - 1 / a k)) atTop (𝓝 putnam_2014_a3_solution) :=
sorry

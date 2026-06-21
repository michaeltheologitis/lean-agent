import Mathlib

open Metric Set EuclideanGeometry Filter Topology

noncomputable abbrev putnam_1970_b1_solution : ℝ := sorry
/--
Evaluate the infinite product $\lim_{n \to \infty} \frac{1}{n^4} \prod_{i = 1}^{2n} (n^2 + i^2)^{1/n}$.
-/
theorem putnam_1970_b1
: Tendsto (fun n => 1/(n^4) * ∏ i ∈ Finset.Icc (1 : ℤ) (2*n), ((n^2 + i^2) : ℝ)^((1 : ℝ)/n)) atTop (𝓝 putnam_1970_b1_solution) :=
sorry

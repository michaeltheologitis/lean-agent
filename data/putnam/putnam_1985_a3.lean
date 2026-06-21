import Mathlib

open Set Filter Topology Real

noncomputable abbrev putnam_1985_a3_solution : ℝ → ℝ := sorry
/--
Let $d$ be a real number. For each integer $m \geq 0$, define a sequence $\{a_m(j)\}$, $j=0,1,2,\dots$ by the condition
\begin{align*}
a_m(0) &= d/2^m, \\
a_m(j+1) &= (a_m(j))^2 + 2a_m(j), \qquad j \geq 0.
\end{align*}
Evaluate $\lim_{n \to \infty} a_n(n)$.
-/
theorem putnam_1985_a3
(d : ℝ)
(a : ℕ → ℕ → ℝ)
(ha0 : ∀ m : ℕ, a m 0 = d / 2 ^ m)
(ha : ∀ m : ℕ, ∀ j : ℕ, a m (j + 1) = (a m j) ^ 2 + 2 * a m j)
: Tendsto (fun n ↦ a n n) atTop (𝓝 (putnam_1985_a3_solution d)) :=
sorry

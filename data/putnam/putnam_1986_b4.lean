import Mathlib

open  Real Equiv Polynomial Filter Topology

abbrev putnam_1986_b4_solution : Prop := sorry
/--
For a positive real number $r$, let $G(r)$ be the minimum value of $|r - \sqrt{m^2+2n^2}|$ for all integers $m$ and $n$. Prove or disprove the assertion that $\lim_{r\to \infty}G(r)$ exists and equals $0$.
-/
theorem putnam_1986_b4
(G : ℝ → ℝ)
(hGeq : ∀ r : ℝ, ∃ m n : ℤ, G r = |r - sqrt (m ^ 2 + 2 * n ^ 2)|)
(hGlb : ∀ r : ℝ, ∀ m n : ℤ, G r ≤ |r - sqrt (m ^ 2 + 2 * n ^ 2)|)
: (Tendsto G atTop (𝓝 0) ↔ putnam_1986_b4_solution) :=
sorry

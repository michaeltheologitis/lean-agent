import Mathlib

open Nat Set MeasureTheory Topology Filter

abbrev putnam_1973_a2_solution : Prop := sorry
/--
Consider an infinite series whose $n$th term is given by $\pm \frac{1}{n}$, where the actual values of the $\pm$ signs repeat in blocks of $8$ (so the $\frac{1}{9}$ term has the same sign as the $\frac{1}{1}$ term, and so on). Call such a sequence balanced if each block contains four $+$ and four $-$ signs. Prove that being balanced is a sufficient condition for the sequence to converge. Is being balanced also necessary for the sequence to converge?
-/
theorem putnam_1973_a2
(L : List ℝ)
(hL : L.length = 8 ∧ ∀ i : Fin L.length, L[i] = 1 ∨ L[i] = -1)
(pluses : ℕ)
(hpluses : pluses = {i : Fin L.length | L[i] = 1}.ncard)
(S : ℕ → ℝ)
(hS : S = fun n : ℕ ↦ ∑ i ∈ Finset.Icc 1 n, L[i % 8]/i)
: (pluses = 4 → ∃ l : ℝ, Tendsto S atTop (𝓝 l)) ∧ (putnam_1973_a2_solution ↔ ((∃ l : ℝ, Tendsto S atTop (𝓝 l)) → pluses = 4)) :=
sorry

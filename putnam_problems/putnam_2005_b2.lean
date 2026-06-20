import Mathlib

open Nat Set

-- Note: uses ℕ → ℕ instead of Fin n → ℕ
abbrev putnam_2005_b2_solution : Set (ℕ × (ℕ → ℤ)) := sorry
/--
Find all positive integers $n,k_1,\dots,k_n$ such that $k_1+\cdots+k_n=5n-4$ and $\frac{1}{k_1}+\cdots+\frac{1}{k_n}=1$.
-/
theorem putnam_2005_b2
: {((n : ℕ), (k : ℕ → ℤ)) | (n > 0) ∧ (∀ i ∈ Finset.range n, k i > 0) ∧ (∑ i ∈ Finset.range n, k i = 5 * n - 4) ∧ (∑ i : Finset.range n, (1 : ℝ) / (k i) = 1)} = putnam_2005_b2_solution :=
sorry

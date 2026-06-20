import Mathlib

open MeasureTheory
open scoped ProbabilityTheory
open scoped Topology
open scoped Real

noncomputable abbrev putnam_2024_b4_solution : ℝ := sorry
/--
Let $n$ be a positive integer. Set $a_{n, 0} = 1$. For $k \geq 0$
choose an integer $m_{n, k}$ uniformly at random from the set
$\{1, 2, \ldots, n\}$, and let
$$a_{n, k+1} = \begin{cases}
a_{n, k} + 1 & \text{if } m_{n, k} > a_{n, k} \\
a_{n, k} & \text{ if } m_{n, k} = a_{n, k} \\
a_{n, k} -1 & \text{if } m_{n, k} < a_{n, k} \end{cases}$$.
Let $E(n)$ be the expected value of $a_{n, n}$. Determine
$\lim_{n \to \infty} E(n)/n$.
-/
theorem putnam_2024_b4
    {Ω : Type*}
    [MeasureSpace Ω]
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (m a : ℕ → ℕ → Ω → ℤ)
    (h₀ : ∀ n > 0, a n 0 = 1)
    (h₁ : ∀ n k, 0 < n → pdf.IsUniform (m n k) (Set.Icc 1 n) ℙ (ProbabilityTheory.uniformOn <| Set.Icc 1 n))
    (h₂ : ∀ n k ω, 0 < n →
      a n (k + 1) ω =
        if m n k ω > a n k ω then
          a n k ω + 1
        else if m n k ω = a n k ω then
          a n k ω
        else
          a n k ω - 1)
    (h₃ : ProbabilityTheory.iIndepFun m.uncurry ℙ) :
    Filter.Tendsto (fun n => (∫ ω, a n n ω : ℝ) / n) Filter.atTop (𝓝 putnam_2024_b4_solution) :=
  sorry

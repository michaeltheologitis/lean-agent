import Mathlib

open Filter Topology Real

abbrev putnam_1995_a5_solution : Prop := sorry
/--
Let $x_{1},x_{2},\dots,x_{n}$ be differentiable (real-valued) functions of a single variable $f$ which satisfy \begin{align*} \frac{dx_{1}}{dt} &= a_{11}x_{1} + a_{12}x_{2} + \cdots + a_{1n}x_{n} \ \frac{dx_{2}}{dt} &= a_{21}x_{1} + a_{22}x_{2} + \cdots + a_{2n}x_{n} \ \vdots && \vdots \ \frac{dx_{n}}{dt} &= a_{n1}x_{1} + a_{n2}x_{2} + \cdots + a_{nn}x_{n} \end{align*} for some constants $a_{ij}>0$. Suppose that for all $i$, $x_{i}(t) \to 0$ as $t \to \infty$. Are the functions $x_{1},x_{2},\dots,x_{n}$ necessarily linearly dependent?
-/
theorem putnam_1995_a5 :
  putnam_1995_a5_solution ↔
  (∀ (n : ℕ) (x : Fin n → (ℝ → ℝ)) (a : Fin n → Fin n → ℝ),
    (0 < n) →
    (∀ i, Differentiable ℝ (x i)) →
    (∀ i j, a i j > 0) →
    (∀ t i, (deriv (x i)) t = ∑ j : Fin n, (a i j) * ((x j) t)) →
    (∀ i, Tendsto (x i) atTop (𝓝 0)) →
    ¬(∀ b : Fin n → ℝ, (∀ t : ℝ, ∑ i : Fin n, (b i) * ((x i) t) = 0) →
      (∀ i, b i = 0))) :=
  sorry

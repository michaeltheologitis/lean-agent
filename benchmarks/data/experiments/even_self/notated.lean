-- "notated" condition: the concept is given as a definition + a helper lemma.
-- These are pre-loaded into the environment AND shown to the model.

def IsEven (n : Nat) : Prop := ∃ k, n = 2 * k

theorem isEven_add_self (n : Nat) : IsEven (n + n) := ⟨n, by omega⟩

-- The goal (last theorem in the file). With the lemma above in scope, this is one step.
theorem target (n : Nat) : IsEven (n + n) := sorry

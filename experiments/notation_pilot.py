"""Notation-vs-raw agent experiment (pilot).

Hypothesis: the agent solves Lean problems more reliably when they are stated in
our custom notation (with the notation/lemmas made available) than when stated
in raw, desugared core Lean -- and that the gap widens with difficulty.

Each problem has two CONDITIONS stating the *same* proposition:
  * notated -- imports the candidates authoring layer (notation + helper lemmas);
    the prompt includes a notation cheat-sheet.
  * raw     -- self-contained core-only definitions, no notation, no helpers.

For each (problem x condition x trial) we hand the agent a file containing the
theorem with a `sorry`, let it edit+compile-check that file (a CodeAgent runs
Python, so it can write the file and call `lean_check_compiles`), then the
harness INDEPENDENTLY verdicts the result: the file must compile, contain no
`sorry`/`admit`/`axiom`, and still carry the exact theorem signature we asked
for (so it cannot "win" by weakening the statement).

Usage:
    # validate the Lean side + print prompts, no API calls, no key needed:
    uv run python experiments/notation_pilot.py --dry-run

    # blind agent (compile-check only):
    uv run python experiments/notation_pilot.py --trials 3

    # sighted agent (adds lean_goal proof-state via lean-lsp-mcp):
    uv run --with mcp --with mcpadapt python experiments/notation_pilot.py --sighted --trials 3
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# candidates/ is the Lean project the agent compiles against (core-only, fast).
CANDIDATES = Path("/home/aurasl/projects/gcd/candidates").resolve()
# Per-run scratch/output files live here; gitignored-by-convention, cleaned each run.
WORKDIR = CANDIDATES / "NotationExp" / "_run"

FORBIDDEN = ("sorry", "admit", "axiom")


@dataclass(frozen=True)
class Condition:
    """One way of stating a problem (notated or raw)."""
    name: str
    template: str          # full .lean file with a single `__PROOF__` placeholder
    signature: str         # exact text that must survive in the agent's output
    reference: str         # a known-good `__PROOF__` (proves well-posedness)
    cheatsheet: str        # notation/lemmas described to the agent


@dataclass(frozen=True)
class Problem:
    name: str
    tier: int
    conditions: dict[str, Condition] = field(default_factory=dict)


# --- pilot problem set (seed: one tier-3 CA pair) ----------------------------

CA_LINEAR = Problem(
    name="ca_evolves_linearly",
    tier=3,
    conditions={
        "notated": Condition(
            name="notated",
            template=(
                "import Candidates.CellularAutomata.Basic\n"
                "open CA\n\n"
                "theorem target : (C ⊻ R) evolves linearly := __PROOF__\n"
            ),
            signature="theorem target : (C ⊻ R) evolves linearly :=",
            reference="evolves_linearly_of_additive (by decide)",
            cheatsheet=(
                "A small custom cellular-automata library is already imported "
                "(`open CA`). Available notation and lemmas:\n"
                "- `Config = Int → Bool`, `Rule = Bool → Bool → Bool → Bool`.\n"
                "- Local rules by neighborhood: `L` `C` `R` (left/center/right cell), "
                "`OFF` `ON`, `!p` (not), `p ⋀ q` (and), `p ⋁ q` (or), `p ⊻ q` (xor). "
                "So `C ⊻ R` is the rule 'xor of the centre and right cells'.\n"
                "- `c ⊕ d` : pointwise xor of two configurations.\n"
                "- Statement notation: `f is additive`, `f steps linearly`, "
                "`f evolves linearly`.\n"
                "- A concrete rule's additivity is decidable: `f is additive` is "
                "provable `by decide`.\n"
                "- Lemmas:\n"
                "    `steps_linearly_of_additive  : f is additive → f steps linearly`\n"
                "    `evolves_linearly_of_additive : f is additive → f evolves linearly`\n"
            ),
        ),
        "raw": Condition(
            name="raw",
            template=(
                "import Candidates.NotationExp.RawDefsCA\n"
                "open CARaw\n\n"
                "theorem target :\n"
                "    ∀ (t : Nat) (c d : Config),\n"
                "      evolve centerRight t (xorC c d)\n"
                "        = xorC (evolve centerRight t c) (evolve centerRight t d) := __PROOF__\n"
            ),
            signature="theorem target :",
            reference=(
                "by\n"
                "  intro t c d\n"
                "  induction t with\n"
                "  | zero => rfl\n"
                "  | succ n ih =>\n"
                "      simp only [evolve]; rw [ih]; funext x\n"
                "      simp only [step, xorC, centerRight]\n"
                "      cases evolve centerRight n c x <;> cases evolve centerRight n c (x + 1) <;>\n"
                "        cases evolve centerRight n d x <;> cases evolve centerRight n d (x + 1) <;> rfl"
            ),
            cheatsheet=(
                "Core Lean 4 only, plus these definitions (already imported, "
                "`open CARaw`):\n"
                "- `Config := Int → Bool`\n"
                "- `Rule := Bool → Bool → Bool → Bool`\n"
                "- `step (f : Rule) (c : Config) : Config := "
                "fun x => f (c (x-1)) (c x) (c (x+1))`\n"
                "- `evolve (f : Rule) : Nat → Config → Config` with "
                "`evolve f 0 c = c` and `evolve f (n+1) c = step f (evolve f n c)`\n"
                "- `xorC (c d : Config) : Config := fun x => Bool.xor (c x) (d x)`\n"
                "- `centerRight : Rule := fun _ c r => Bool.xor c r`\n"
                "There is no notation and there are no helper lemmas; prove it from "
                "scratch (hint: induction on `t`, `funext`, and case on the booleans)."
            ),
        ),
    },
)

REGEX_FOIL = Problem(
    name="regex_foil",
    tier=4,
    conditions={
        "notated": Condition(
            name="notated",
            template=(
                "import Candidates.RegularExpressions.Proving\n"
                "open Regex\n\n"
                "theorem target {α : Type} (r s t u : Regex α) :\n"
                "    (r + s) * (t + u) ≃ᵣ (r * t + r * u) + (s * t + s * u) := __PROOF__\n"
            ),
            signature="(r + s) * (t + u) ≃ᵣ (r * t + r * u) + (s * t + s * u) :=",
            reference=(
                "by\n"
                "  calc (r + s) * (t + u)\n"
                "      ≃ᵣ r * (t + u) + s * (t + u)       := concat_union_right r s (t + u)\n"
                "    _ ≃ᵣ (r * t + r * u) + s * (t + u)   := union_congr (concat_union_left r t u) (Sim.refl _)\n"
                "    _ ≃ᵣ (r * t + r * u) + (s * t + s * u) := union_congr (Sim.refl _) (concat_union_left s t u)"
            ),
            cheatsheet=(
                "A custom regex algebra is already imported (`open Regex`). "
                "Available notation and lemmas:\n"
                "- Kleene-algebra notation: `0` (empty language), `1` (empty word), "
                "`r + s` (union), `r * s` (concatenation), `r∗` (star).\n"
                "- `r ≃ᵣ s` : the two regexes match exactly the same words "
                "(language equivalence). It is reflexive/symmetric/transitive and "
                "works in `calc` (use `Sim.refl _` for a reflexivity step).\n"
                "- Congruence (rewrite a subterm): "
                "`union_congr : r ≃ᵣ r' → s ≃ᵣ s' → r + s ≃ᵣ r' + s'`, and "
                "`concat_congr` likewise for `*`.\n"
                "- Algebra laws (each `... ≃ᵣ ...`): `union_comm`, `union_assoc`, "
                "`union_idem`, `emp_union`, `union_emp`, `concat_assoc`, and "
                "distributivity `concat_union_left : r * (s + t) ≃ᵣ r * s + r * t`, "
                "`concat_union_right : (r + s) * t ≃ᵣ r * t + s * t`.\n"
                "Chain these with `calc`."
            ),
        ),
        "raw": Condition(
            name="raw",
            template=(
                "import Candidates.NotationExp.RawDefsRegex\n"
                "open RegexRaw\n\n"
                "theorem target {α : Type} (r s t u : Regex α) :\n"
                "    ∀ w, Matches (.concat (.union r s) (.union t u)) w ↔\n"
                "         Matches (.union (.union (.concat r t) (.concat r u))\n"
                "                         (.union (.concat s t) (.concat s u))) w := __PROOF__\n"
            ),
            signature="∀ w, Matches (.concat (.union r s) (.union t u)) w",
            reference=(
                "by\n"
                "  intro w\n"
                "  constructor\n"
                "  · intro h\n"
                "    cases h with\n"
                "    | cat h1 h2 =>\n"
                "      cases h1 with\n"
                "      | inl hr =>\n"
                "        cases h2 with\n"
                "        | inl ht => exact .inl (.inl (.cat hr ht))\n"
                "        | inr hu => exact .inl (.inr (.cat hr hu))\n"
                "      | inr hs =>\n"
                "        cases h2 with\n"
                "        | inl ht => exact .inr (.inl (.cat hs ht))\n"
                "        | inr hu => exact .inr (.inr (.cat hs hu))\n"
                "  · intro h\n"
                "    cases h with\n"
                "    | inl h =>\n"
                "      cases h with\n"
                "      | inl h => cases h with | cat hr ht => exact .cat (.inl hr) (.inl ht)\n"
                "      | inr h => cases h with | cat hr hu => exact .cat (.inl hr) (.inr hu)\n"
                "    | inr h =>\n"
                "      cases h with\n"
                "      | inl h => cases h with | cat hs ht => exact .cat (.inr hs) (.inl ht)\n"
                "      | inr h => cases h with | cat hs hu => exact .cat (.inr hs) (.inr hu)"
            ),
            cheatsheet=(
                "Core Lean 4 only, plus these definitions (already imported, "
                "`open RegexRaw`):\n"
                "- `Regex α` with constructors `Regex.nil`, `Regex.eps`, "
                "`Regex.char a`, `Regex.union r s`, `Regex.concat r s`, "
                "`Regex.star r` (write them as `.union`, `.concat`, etc. where the "
                "type is known).\n"
                "- `Matches : Regex α → List α → Prop`, the language relation, with "
                "constructors:\n"
                "    `Matches.eps : Matches .eps []`\n"
                "    `Matches.char a : Matches (.char a) [a]`\n"
                "    `Matches.inl : Matches r w → Matches (.union r s) w`\n"
                "    `Matches.inr : Matches s w → Matches (.union r s) w`\n"
                "    `Matches.cat : Matches r w₁ → Matches s w₂ → Matches (.concat r s) (w₁ ++ w₂)`\n"
                "    `Matches.starNil`, `Matches.starCat` for star.\n"
                "There is no notation and there are no helper lemmas. Prove the "
                "biconditional directly by `cases` on the `Matches` hypotheses and "
                "rebuilding with the constructors."
            ),
        ),
    },
)

PROBLEMS = [CA_LINEAR, REGEX_FOIL]


# --- prompt -------------------------------------------------------------------

def build_prompt(problem: Problem, cond: Condition, out_file: Path,
                 sighted: bool = False) -> str:
    rel = out_file.relative_to(CANDIDATES).as_posix()
    abs_path = str(out_file)
    statement_with_sorry = cond.template.replace("__PROOF__", "by\n  sorry")
    sighted_help = (
        "\nYou also have `lean_goal(file_path, line)`: it returns the proof goal "
        "state (hypotheses ⊢ target) at a line in the file. Write the file with a "
        "`sorry` (or a partial proof ending in `sorry`) using write_and_check, then "
        f"call `lean_goal('{abs_path}', <line of the sorry>)` to see exactly what "
        "remains to prove, and use that to choose your next tactics.\n"
        if sighted else ""
    )
    return (
        "You are proving a theorem in Lean 4.\n\n"
        f"{cond.cheatsheet}\n\n"
        f"The file `{rel}` (inside the Lean project `{CANDIDATES}`) currently is:\n\n"
        "```lean\n"
        f"{statement_with_sorry}"
        "```\n\n"
        "Replace the `sorry` with a real proof. You have a tool "
        "`write_and_check(file_path, content)`: it writes `content` to the file "
        "and returns the Lean compile result. Call it with the COMPLETE file "
        "source (the imports and theorem shown above, with `sorry` replaced by "
        "your proof). Iterate until it reports 'status: compiled successfully'.\n"
        f"{sighted_help}"
        "\nRules:\n"
        f"- Use file_path `{rel}`.\n"
        "- Keep the imports, theorem name, and statement EXACTLY as given; only "
        "replace the proof.\n"
        "- Do not use `sorry`, `admit`, or `axiom` in the final proof.\n"
        "- When the file compiles, return the final proof you used."
    )


# --- verdict ------------------------------------------------------------------

def verdict(out_file: Path, cond: Condition, compile_check) -> dict:
    """Independent pass/fail: compiles, no forbidden tokens, signature intact."""
    if not out_file.exists():
        return {"passed": False, "reason": "no output file"}
    text = out_file.read_text(encoding="utf-8")
    if cond.signature not in text:
        return {"passed": False, "reason": "theorem signature was altered/missing"}
    lowered = text.lower()
    bad = [tok for tok in FORBIDDEN if tok in lowered]
    if bad:
        return {"passed": False, "reason": f"forbidden token(s): {bad}"}
    result = compile_check(out_file)
    ok = "status: compiled successfully" in result
    return {"passed": ok, "reason": "compiled" if ok else "did not compile",
            "compile_output": result}


def make_compile_check():
    from lean_agent.lean_tools import lean_check_compiles

    def check(out_file: Path) -> str:
        return lean_check_compiles.forward(
            str(CANDIDATES), str(out_file.relative_to(CANDIDATES)), 120
        )
    return check


# --- agent tool ---------------------------------------------------------------
# The CodeAgent sandbox forbids `open`, so the agent cannot write files with
# Python I/O. Give it one tool that writes a Lean file and compile-checks it.

from smolagents import tool  # noqa: E402


@tool
def write_and_check(file_path: str, content: str) -> str:
    """Write a Lean source file and compile-check it in one step.

    Args:
        file_path: Path to the `.lean` file to write, inside the Lean project.
            Relative paths are interpreted from the project root.
        content: The complete Lean source to write to that file.
    """
    from lean_agent.lean_tools import lean_check_compiles

    root = CANDIDATES
    path = Path(file_path)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if root not in (path, *path.parents):
        return f"error: file_path must be inside the project {root}"
    if path.suffix != ".lean":
        return "error: file_path must be a .lean file"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return lean_check_compiles.forward(str(root), str(path.relative_to(root)), 120)


# --- model --------------------------------------------------------------------

def build_model():
    """Build the agent model from the Nebius / Token Factory settings in
    lean-agent/.env (NEBIUS_API_KEY / NEBIUS_MODEL_ID / NEBIUS_API_BASE).

    `max_tokens=4096` caps each generation so a reasoning model cannot run past
    the provider's ~600s gateway window (the 504 we hit before); `max_retries=0`
    keeps a slow call from silently multiplying into several."""
    from smolagents import OpenAIServerModel
    from lean_agent.settings import get_settings

    s = get_settings()
    if not s.api_key:
        raise SystemExit("No model API key found (NEBIUS_API_KEY) in lean-agent/.env.")
    return OpenAIServerModel(
        model_id=s.model_id,
        api_base=s.api_base,
        api_key=s.api_key,
        max_tokens=4096,
        client_kwargs={"timeout": 180, "max_retries": 0},
    )


# --- run ----------------------------------------------------------------------

def run_trial(problem: Problem, cond: Condition, trial: int, model, compile_check,
              extra_tools=(), sighted: bool = False) -> dict:
    from smolagents import CodeAgent

    out_file = WORKDIR / f"{problem.name}__{cond.name}__t{trial}.lean"
    out_file.write_text(cond.template.replace("__PROOF__", "by\n  sorry"), encoding="utf-8")

    agent = CodeAgent(tools=[write_and_check, *extra_tools], model=model, max_steps=4)
    prompt = build_prompt(problem, cond, out_file, sighted=sighted)

    record = {"problem": problem.name, "tier": problem.tier,
              "condition": cond.name, "trial": trial, "sighted": sighted}
    try:
        agent.run(prompt)
    except Exception as exc:  # noqa: BLE001 -- record agent/API failures, keep going
        record |= {"passed": False, "reason": f"agent error: {type(exc).__name__}: {exc}"}
        return record

    record |= verdict(out_file, cond, compile_check)
    usage = agent.monitor.get_total_token_counts()
    record |= {
        "steps": len([s for s in agent.memory.steps if getattr(s, "token_usage", None)]),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }
    return record


def dry_run(compile_check, problems) -> None:
    print("=== DRY RUN: validating reference proofs + showing prompts ===\n")
    for problem in problems:
        for cond in problem.conditions.values():
            out_file = WORKDIR / f"{problem.name}__{cond.name}__ref.lean"
            out_file.write_text(cond.template.replace("__PROOF__", cond.reference), encoding="utf-8")
            result = compile_check(out_file)
            ok = "status: compiled successfully" in result
            print(f"[{problem.name} / {cond.name}] reference proof compiles: "
                  f"{'YES' if ok else 'NO'}")
            if not ok:
                print(result)
            print(f"\n--- prompt ({problem.name} / {cond.name}) ---")
            print(build_prompt(problem, cond, out_file))
            print("-" * 70, "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate Lean side + print prompts; no API calls")
    parser.add_argument("--only", type=str, default=None,
                        help="run only the problem with this name")
    parser.add_argument("--sighted", action="store_true",
                        help="also give the agent lean_goal (proof-state) via "
                             "lean-lsp-mcp; needs `uv run --with mcp --with mcpadapt`")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    WORKDIR.mkdir(parents=True, exist_ok=True)
    compile_check = make_compile_check()

    problems = [p for p in PROBLEMS if args.only is None or p.name == args.only]
    if not problems:
        raise SystemExit(f"no problem named {args.only!r}; have: "
                         f"{[p.name for p in PROBLEMS]}")

    if args.dry_run:
        dry_run(compile_check, problems)
        return

    model = build_model()

    def run_all(extra_tools=(), sighted=False):
        out = []
        for problem in problems:
            for cond in problem.conditions.values():
                for trial in range(1, args.trials + 1):
                    tag = "sighted" if sighted else "blind"
                    print(f"running [{tag}] {problem.name} / {cond.name} / trial {trial} ...")
                    rec = run_trial(problem, cond, trial, model, compile_check,
                                    extra_tools=extra_tools, sighted=sighted)
                    print(f"  -> {'PASS' if rec.get('passed') else 'FAIL'} "
                          f"({rec.get('reason')})")
                    out.append(rec)
        return out

    if args.sighted:
        # Load ONLY lean_goal from lean-lsp-mcp (keep the toolset tiny for small
        # models). Needs `mcp` + `mcpadapt`: run with
        #   uv run --with mcp --with mcpadapt python experiments/notation_pilot.py --sighted ...
        from mcp import StdioServerParameters
        from smolagents import ToolCollection

        server = StdioServerParameters(command="uvx", args=["lean-lsp-mcp"],
                                       env={**os.environ})
        print("starting lean-lsp-mcp (first call starts `lake serve` on candidates) ...")
        with ToolCollection.from_mcp(server, trust_remote_code=True,
                                     structured_output=False) as tc:
            goal = next((t for t in tc.tools if t.name == "lean_goal"), None)
            if goal is None:
                raise SystemExit("lean_goal not found in lean-lsp-mcp tools")
            results = run_all(extra_tools=[goal], sighted=True)
    else:
        results = run_all()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(__file__).resolve().parent / f"results_{stamp}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== summary (pass rate by condition) ===")
    for problem in problems:
        for cname in problem.conditions:
            cell = [r for r in results
                    if r["problem"] == problem.name and r["condition"] == cname]
            passed = sum(1 for r in cell if r.get("passed"))
            print(f"{problem.name} / {cname}: {passed}/{len(cell)} passed")
    print(f"\nfull results: {out}")


if __name__ == "__main__":
    main()

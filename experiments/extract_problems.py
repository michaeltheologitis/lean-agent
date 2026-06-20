"""Extract PutnamBench problems into answer-free `sorry`-stubs.

Uses PutnamBench's own loader (pulled from their branch) to enumerate problems,
then writes each problem's source to `putnam_problems/` with the ground-truth
answer comment removed. The proof — and any `..._solution := sorry` — stays as
`sorry`; the agent fills them in. This regenerates the local problem folder
reproducibly from their extractor.

Run:  uv run python experiments/extract_problems.py
"""

from __future__ import annotations

from pathlib import Path

from lean_agent.putnambench.putnam_loader import load_problems

ROOT = Path(__file__).resolve().parents[1]
REPO = str((ROOT / "PutnamBench").resolve())
OUT = ROOT / "putnam_problems"


def strip_answer_comments(text: str) -> tuple[str, bool]:
    """Drop the ground-truth answer: the `-- ...` comment line(s) immediately
    following a `..._solution ... := sorry` def. Everything else (the `:= sorry`
    stubs and the `/-- statement -/` docstring) is kept verbatim."""
    out, after_solution, stripped = [], False, False
    for line in text.splitlines():
        s = line.strip()
        if after_solution and s.startswith("--"):
            stripped = True            # this is the answer comment; drop it
            continue
        after_solution = ("_solution" in s) and (":= sorry" in s)
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), stripped


def main() -> None:
    OUT.mkdir(exist_ok=True)
    problems = load_problems(REPO)
    n_stripped = 0
    for p in problems:
        cleaned, stripped = strip_answer_comments(p.raw)
        (OUT / f"{p.name}.lean").write_text(cleaned, encoding="utf-8")
        n_stripped += stripped
    print(f"wrote {len(problems)} problems to {OUT}/")
    print(f"stripped answer comments from {n_stripped} files")


if __name__ == "__main__":
    main()

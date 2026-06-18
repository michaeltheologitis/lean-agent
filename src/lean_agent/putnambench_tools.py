from __future__ import annotations

from .putnambench.putnam_loader import Problem, load_problems
from .putnambench.harness import run_benchmark, score_report
from .putnambench.verify import verify_proof
from smolagents import tool
import random

@tool
def get_putnambench_problems(tags: list[str] | None = None, years: tuple[int, int] | None = None) -> list[Problem]:
    """
    Load PutnamBench problems, optionally filtering by tags and/or years.

    Args:
        tags: keep only problems having at least one of these tags.
        years: inclusive (min_year, max_year) filter.

    Returns:
        A list of `Problem` objects matching the specified filters.
    """
    return load_problems("PutnamBench", tags=tags, years=years)

@tool
def get_problem_statement(problem: Problem) -> str:
    """Return the informal statement of a PutnamBench problem, which is what the agent should attempt to solve. 
    
    Args:
        problem: The `Problem` object for which to extract the informal statement.

    Returns:
        The informal statement of the problem.
    """
    return problem.get_informal_statement()

@tool
def verify_putnambench_proof(problem: Problem, proof: str) -> bool:
    """Verify a proof for a PutnamBench problem.

    Args:
        problem: The `Problem` object representing the problem to verify against.
        proof: A string containing the proof in Lean to verify.
    Returns:
        True if the proof is correct, False otherwise. 
    """
    return verify_proof(problem, proof)


"""The unit the agent operates on — pure data.

A `Problem` is split from a `.lean` file by the benchmark loaders: the `preamble` (imports +
definitions/lemmas above the goal) is pre-loaded into both the Lean environment and the system
prompt; the `statement` is the target `theorem ... :=` the agent must prove.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Problem:
    name: str
    benchmark: str
    preamble: str       # imports + given definitions (pre-warms the env AND the system prompt)
    statement: str      # the target `theorem <name> ... :=`  (no sorry)
    informal: str = ""  # informal statement, if known

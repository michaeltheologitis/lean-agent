"""Plumbing smoke test: load lean-lsp-mcp tools into smolagents and call lean_goal.

No model/API. Confirms the MCP server starts, its tools load, the LSP attaches to
the candidates project, and lean_goal returns a real proof state at a `sorry`.

Run:
    uv run --with mcp --with mcpadapt python experiments/_smoke_lsp.py
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp import StdioServerParameters
from smolagents import ToolCollection

CANDIDATES = Path("/home/aurasl/projects/gcd/candidates").resolve()
SMOKE = CANDIDATES / "NotationExp" / "_smoke.lean"

server = StdioServerParameters(
    command="uvx",
    args=["lean-lsp-mcp"],
    env={**os.environ},
)

print("starting lean-lsp-mcp (first run may download + start `lake serve`) ...")
with ToolCollection.from_mcp(server, trust_remote_code=True) as tc:
    tools = {t.name: t for t in tc.tools}
    print("loaded tools:", sorted(tools))
    assert "lean_goal" in tools, "lean_goal not exposed"
    g = tools["lean_goal"]
    print("\ncalling lean_goal on the sorry (line 2) ...")
    out = g(file_path=str(SMOKE), line=2)
    print("=== lean_goal output ===")
    print(out)

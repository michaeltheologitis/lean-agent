# Lean Tool Integration Notes

This branch is for attaching Lean support to the upstream smolagents
`CodeAgent` scaffold, without continuing the old custom `gcd-agent`.

## Current Tool Surface

For now, expose only compile checking.

`LEAN_TOOLS` contains one tool:

- `lean_check_compiles(project_path: str, file_path: str = "", timeout_seconds: int = 120)
  -> str`

Behavior:

- with no `file_path`, it runs `lake build`;
- with a `file_path`, it runs `lake env lean <file>`;
- it returns a compact status, exit code, command, stdout, and stderr;
- it does not inspect goals, search declarations, scan source files, or edit files.

This is deliberately narrow. The first agent tests should verify that the agent
can ask "does this compile?" and use the answer correctly before it receives
richer Lean affordances.

## Inspiration From `lean-lsp-mcp`

I inspected `/home/aurasl/lean-lsp-mcp`. The relevant architecture is:

- it runs Lean through `leanclient` and a persistent LSP client;
- project roots are inferred by walking upward to `lean-toolchain`;
- the active project/client lives in a lifespan context and is reused across
  tool calls;
- its build path closes/restarts the LSP client after rebuilding;
- file tools first ensure the LSP client is attached to the correct project;
- stdout/stderr from Lean startup is captured so tool responses stay focused.

That is the right direction once we want the agent to understand Lean state.
But it should be a later layer, not the first smolagents tool surface.

## Later LSP Shape

When we are ready to go beyond compile checking, prefer a separate adapter
module rather than growing `lean_check_compiles`:

- one object owns project-root inference and client lifecycle;
- one small group of tools exposes diagnostics/goals/hover information;
- build/restart remains explicit;
- write-capable tools stay out until we have clear isolation and revert
  semantics.

No API key is needed for the current compile-check work. Model-backed agent
testing uses Token Factory from `lean-agent/.env`.

Put the key here:

```dotenv
NEBIUS_API_KEY='...'
```

The default model/base are:

```dotenv
NEBIUS_MODEL_ID='deepseek-ai/DeepSeek-V3.2-fast'
NEBIUS_API_BASE='https://api.tokenfactory.nebius.com/v1/'
```

`TOKEN_FACTORY_API_KEY` is also accepted as an alias for the key. Token Factory
does not currently list `deepseek-v4-flash` on this endpoint; the fast DeepSeek
model ID available through `/models` is `deepseek-ai/DeepSeek-V3.2-fast`.

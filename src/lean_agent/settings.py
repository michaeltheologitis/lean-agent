"""Runtime configuration.

Provider-agnostic but **OpenAI-first**: the milestone pins OpenAI `gpt-5.4-nano`, so that
is the default model + base. Any OpenAI-compatible provider (Nebius / Token Factory / a
local vLLM endpoint) works by setting its env vars, which take precedence over the OpenAI
defaults when present.

Resolution order per field (first non-empty wins):

    api_key   : OPENAI_API_KEY → NEBIUS_API_KEY → TOKEN_FACTORY_API_KEY
    model_id  : OPENAI_MODEL_ID → NEBIUS_MODEL_ID → TOKEN_FACTORY_MODEL → gpt-5.4-nano
    api_base  : OPENAI_API_BASE → OPENAI_BASE_URL → NEBIUS_API_BASE
                → TOKEN_FACTORY_BASE_URL → https://api.openai.com/v1

To run against OpenAI: set `OPENAI_API_KEY` (model/base default correctly). To run against
Nebius/Token Factory instead: leave `OPENAI_API_KEY` empty and set the provider's key +
model + base.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_ID = "gpt-5.4-nano"
DEFAULT_API_BASE = "https://api.openai.com/v1"


@dataclass(frozen=True)
class Settings:
    """Runtime configuration.

    `api_key` / `api_base` mirror smolagents' `OpenAIServerModel` kwargs so swapping
    OpenAI-compatible providers is just an env change.
    """
    api_key: str | None = None
    model_id: str = DEFAULT_MODEL_ID
    api_base: str | None = DEFAULT_API_BASE
    log_dir: Path = PROJECT_ROOT / "logs"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    settings = Settings(
        api_key=_first_env("OPENAI_API_KEY", "NEBIUS_API_KEY", "TOKEN_FACTORY_API_KEY"),
        model_id=_first_env(
            "OPENAI_MODEL_ID", "NEBIUS_MODEL_ID", "TOKEN_FACTORY_MODEL"
        ) or DEFAULT_MODEL_ID,
        api_base=_first_env(
            "OPENAI_API_BASE", "OPENAI_BASE_URL", "NEBIUS_API_BASE", "TOKEN_FACTORY_BASE_URL"
        ) or DEFAULT_API_BASE,
    )
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings

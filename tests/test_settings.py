"""Tests for the settings loader (OpenAI-first resolution)."""

from __future__ import annotations

from lean_agent import settings as settings_module

_ALL_ENV = (
    "OPENAI_API_KEY", "OPENAI_MODEL_ID", "OPENAI_API_BASE", "OPENAI_BASE_URL",
    "NEBIUS_API_KEY", "NEBIUS_MODEL_ID", "NEBIUS_API_BASE",
    "TOKEN_FACTORY_API_KEY", "TOKEN_FACTORY_MODEL", "TOKEN_FACTORY_BASE_URL",
    "LEAN_VERSION", "LEAN_PROJECT",
)


def _fresh(monkeypatch):
    settings_module.get_settings.cache_clear()
    for name in _ALL_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)


def test_dataclass_defaults():
    s = settings_module.Settings()
    assert s.api_key is None
    assert s.model_id == settings_module.DEFAULT_MODEL_ID == "gpt-5.4-nano"
    assert s.api_base == settings_module.DEFAULT_API_BASE == "https://api.openai.com/v1"
    assert s.log_dir == settings_module.PROJECT_ROOT / "logs"


def test_no_key_defaults_to_openai(monkeypatch):
    _fresh(monkeypatch)
    s = settings_module.get_settings()
    assert s.api_key is None
    assert s.model_id == "gpt-5.4-nano"
    assert s.api_base == "https://api.openai.com/v1"


def test_openai_key_and_overrides(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("OPENAI_MODEL_ID", "gpt-5.4-mini")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    s = settings_module.get_settings()
    assert s.api_key == "sk-openai"
    assert s.model_id == "gpt-5.4-mini"


def test_openai_takes_precedence_over_nebius(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("NEBIUS_API_KEY", "nb-test")
    monkeypatch.setenv("NEBIUS_MODEL_ID", "deepseek-ai/DeepSeek-V3.2-fast")
    s = settings_module.get_settings()
    assert s.api_key == "sk-openai"
    # model_id falls through to NEBIUS only because OPENAI_MODEL_ID is unset
    assert s.model_id == "deepseek-ai/DeepSeek-V3.2-fast"


def test_nebius_used_when_openai_absent(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("NEBIUS_API_KEY", "nb-test")
    monkeypatch.setenv("NEBIUS_MODEL_ID", "deepseek-ai/DeepSeek-V3.2-fast")
    monkeypatch.setenv("NEBIUS_API_BASE", "https://api.tokenfactory.nebius.com/v1/")
    s = settings_module.get_settings()
    assert s.api_key == "nb-test"
    assert s.model_id == "deepseek-ai/DeepSeek-V3.2-fast"
    assert s.api_base == "https://api.tokenfactory.nebius.com/v1/"


def test_token_factory_aliases(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "tf-test")
    monkeypatch.setenv("TOKEN_FACTORY_MODEL", "some-model")
    monkeypatch.setenv("TOKEN_FACTORY_BASE_URL", "https://token-factory.test/v1")
    s = settings_module.get_settings()
    assert s.api_key == "tf-test"
    assert s.model_id == "some-model"
    assert s.api_base == "https://token-factory.test/v1"


def test_lean_defaults(monkeypatch):
    _fresh(monkeypatch)
    s = settings_module.get_settings()
    assert s.lean_version == "v4.29.1"
    assert s.lean_project is None


def test_lean_overrides(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("LEAN_VERSION", "v4.24.0")
    monkeypatch.setenv("LEAN_PROJECT", "/tmp/mathlib-proj")
    s = settings_module.get_settings()
    assert s.lean_version == "v4.24.0"
    assert s.lean_project == "/tmp/mathlib-proj"


def test_is_cached(monkeypatch):
    _fresh(monkeypatch)
    assert settings_module.get_settings() is settings_module.get_settings()

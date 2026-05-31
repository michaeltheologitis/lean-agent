"""Tests for the settings loader."""

from __future__ import annotations

from lean_agent import settings as settings_module


def _reset_cache():
    settings_module.get_settings.cache_clear()


def _clear_model_env(monkeypatch):
    for name in (
        "NEBIUS_API_KEY",
        "NEBIUS_MODEL_ID",
        "NEBIUS_API_BASE",
        "TOKEN_FACTORY_API_KEY",
        "TOKEN_FACTORY_MODEL",
        "TOKEN_FACTORY_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL_ID",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_dataclass_defaults():
    """Settings carries its own defaults — no env or .env required."""
    s = settings_module.Settings()
    assert s.api_key is None
    assert s.model_id == settings_module.DEFAULT_MODEL_ID
    assert s.api_base == settings_module.DEFAULT_API_BASE
    assert s.log_dir == settings_module.PROJECT_ROOT / "logs"


def test_get_settings_no_key(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    s = settings_module.get_settings()
    assert s.api_key is None
    assert s.model_id == settings_module.DEFAULT_MODEL_ID
    assert s.api_base == settings_module.DEFAULT_API_BASE


def test_get_settings_reads_nebius_api_key(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("NEBIUS_API_KEY", "nb-test")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    assert settings_module.get_settings().api_key == "nb-test"


def test_get_settings_reads_nebius_model_and_api_base(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("NEBIUS_MODEL_ID", "deepseek-ai/DeepSeek-V4-Pro")
    monkeypatch.setenv("NEBIUS_API_BASE", "https://example.test/v1")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    settings = settings_module.get_settings()
    assert settings.model_id == "deepseek-ai/DeepSeek-V4-Pro"
    assert settings.api_base == "https://example.test/v1"


def test_get_settings_accepts_token_factory_aliases(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "tf-test")
    monkeypatch.setenv("TOKEN_FACTORY_MODEL", "deepseek-ai/DeepSeek-V3.2-fast")
    monkeypatch.setenv("TOKEN_FACTORY_BASE_URL", "https://token-factory.test/v1")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    settings = settings_module.get_settings()
    assert settings.api_key == "tf-test"
    assert settings.model_id == "deepseek-ai/DeepSeek-V3.2-fast"
    assert settings.api_base == "https://token-factory.test/v1"


def test_get_settings_accepts_openai_compatible_aliases(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-compatible")
    monkeypatch.setenv("OPENAI_MODEL_ID", "compatible-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:8001/v1")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    settings = settings_module.get_settings()
    assert settings.api_key == "sk-compatible"
    assert settings.model_id == "compatible-model"
    assert settings.api_base == "http://localhost:8001/v1"


def test_nebius_env_takes_precedence(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("NEBIUS_API_KEY", "nb-test")
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "tf-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("NEBIUS_MODEL_ID", "deepseek-ai/DeepSeek-V3.2-fast")
    monkeypatch.setenv("OPENAI_MODEL_ID", "gpt-4.1-nano")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    settings = settings_module.get_settings()
    assert settings.api_key == "nb-test"
    assert settings.model_id == "deepseek-ai/DeepSeek-V3.2-fast"


def test_is_cached(monkeypatch):
    _reset_cache()
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)
    a = settings_module.get_settings()
    b = settings_module.get_settings()
    assert a is b

"""Tests for the settings loader."""

from __future__ import annotations

from lean_agent import settings as settings_module


def _reset_cache():
    settings_module.get_settings.cache_clear()


def _clear_env(monkeypatch):
    for k in ("API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_dataclass_defaults():
    """Settings carries its own defaults — no env or .env required."""
    s = settings_module.Settings()
    assert s.api_key is None
    assert s.model_id == "gpt-5.4-nano"
    assert s.api_base is None
    assert s.log_dir == settings_module.PROJECT_ROOT / "logs"


def test_get_settings_no_key(monkeypatch):
    _reset_cache()
    _clear_env(monkeypatch)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    s = settings_module.get_settings()
    assert s.api_key is None
    assert s.model_id == "gpt-5.4-nano"


def test_get_settings_reads_api_key(monkeypatch):
    _reset_cache()
    _clear_env(monkeypatch)
    monkeypatch.setenv("API_KEY", "sk-generic")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    assert settings_module.get_settings().api_key == "sk-generic"


def test_openai_api_key_is_fallback(monkeypatch):
    _reset_cache()
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-openai-env")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    assert settings_module.get_settings().api_key == "sk-from-openai-env"


def test_api_key_wins_over_openai_api_key(monkeypatch):
    _reset_cache()
    _clear_env(monkeypatch)
    monkeypatch.setenv("API_KEY", "sk-generic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)

    assert settings_module.get_settings().api_key == "sk-generic"


def test_is_cached(monkeypatch):
    _reset_cache()
    _clear_env(monkeypatch)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **kw: None)
    a = settings_module.get_settings()
    b = settings_module.get_settings()
    assert a is b

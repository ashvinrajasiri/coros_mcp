import pytest
from coros_mcp.config import load_config, ConfigError


def test_load_config_requires_email_password(monkeypatch):
    monkeypatch.delenv("COROS_EMAIL", raising=False)
    monkeypatch.delenv("COROS_PASSWORD", raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_defaults_region(monkeypatch):
    monkeypatch.setenv("COROS_EMAIL", "a@b.com")
    monkeypatch.setenv("COROS_PASSWORD", "secret")
    monkeypatch.delenv("COROS_REGION", raising=False)
    cfg = load_config()
    assert cfg.email == "a@b.com"
    assert cfg.password == "secret"
    assert cfg.region == "us"

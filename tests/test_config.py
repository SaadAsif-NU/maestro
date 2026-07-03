from __future__ import annotations

from maestro.config import Settings

_KEYS = [
    "MAESTRO_LOG_LEVEL",
    "MAESTRO_SIM_DELAY",
    "MAESTRO_MAX_CONCURRENCY",
    "MAESTRO_MODEL",
    "MAESTRO_MAX_RUNS",
    "MAESTRO_RUN_TIMEOUT",
    "MAESTRO_MAX_CONCURRENT_RUNS",
    "MAESTRO_CORS_ORIGINS",
]


def test_defaults(monkeypatch):
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)
    s = Settings.from_env()
    assert s.log_level == "INFO"
    assert s.sim_delay == 0.02
    assert s.max_concurrency == 3
    assert s.model_override is None
    assert s.max_runs == 200
    assert s.run_timeout_s == 300.0
    assert s.max_concurrent_runs == 8
    assert s.cors_origins == ()


def test_overrides(monkeypatch):
    monkeypatch.setenv("MAESTRO_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("MAESTRO_MODEL", "gpt-5")
    monkeypatch.setenv("MAESTRO_CORS_ORIGINS", "http://a.com, http://b.com")
    s = Settings.from_env()
    assert s.max_concurrency == 1
    assert s.model_override == "gpt-5"
    assert s.cors_origins == ("http://a.com", "http://b.com")


def test_invalid_numbers_fall_back(monkeypatch):
    monkeypatch.setenv("MAESTRO_MAX_RUNS", "not-a-number")
    monkeypatch.setenv("MAESTRO_RUN_TIMEOUT", "x")
    s = Settings.from_env()
    assert s.max_runs == 200
    assert s.run_timeout_s == 300.0


def test_floors(monkeypatch):
    monkeypatch.setenv("MAESTRO_MAX_CONCURRENCY", "0")
    monkeypatch.setenv("MAESTRO_MAX_CONCURRENT_RUNS", "0")
    s = Settings.from_env()
    assert s.max_concurrency == 1 and s.max_concurrent_runs == 1

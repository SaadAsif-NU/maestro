from __future__ import annotations

import os

from maestro.env import load_env


def test_load_env_sets_vars(tmp_path):
    env = tmp_path / ".env"
    env.write_text('MAESTRO_T_FOO=bar\n# a comment\nMAESTRO_T_Q="a b c"\nMAESTRO_T_EMPTY=\n')
    for k in ("MAESTRO_T_FOO", "MAESTRO_T_Q", "MAESTRO_T_EMPTY"):
        os.environ.pop(k, None)
    try:
        assert load_env(env) is True
        assert os.environ["MAESTRO_T_FOO"] == "bar"
        assert os.environ["MAESTRO_T_Q"] == "a b c"  # quotes stripped
        assert os.environ["MAESTRO_T_EMPTY"] == ""
    finally:
        for k in ("MAESTRO_T_FOO", "MAESTRO_T_Q", "MAESTRO_T_EMPTY"):
            os.environ.pop(k, None)


def test_load_env_does_not_override_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("MAESTRO_T_FOO=fromfile\n")
    monkeypatch.setenv("MAESTRO_T_FOO", "fromenv")
    load_env(env)
    assert os.environ["MAESTRO_T_FOO"] == "fromenv"  # the real environment wins


def test_load_env_missing_file(tmp_path):
    assert load_env(tmp_path / "nope.env") is False

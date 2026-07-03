"""Minimal .env loader (no dependency).

Loads ``KEY=VALUE`` lines from a ``.env`` file into the process environment so a
user can keep their API key in a file instead of exporting it in the shell every
time. Values already set in the real environment win, and ``.env`` is gitignored
so secrets never reach source control.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path = ".env") -> bool:
    """Load ``path`` into ``os.environ`` (without overriding existing vars).

    Returns ``True`` if a file was found and read.
    """
    file = Path(path)
    if not file.is_file():
        return False
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
    return True

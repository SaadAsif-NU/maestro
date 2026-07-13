from __future__ import annotations

import os

# Make the offline brain instant so the whole suite runs fast.
os.environ["MAESTRO_SIM_DELAY"] = "0"

# Keep the suite hermetic and offline: clear the provider keys so neither a
# developer's real .env (loaded via setdefault, which never overrides these) nor
# an exported shell variable can flip the tests onto a live model. Tests that
# want a real brain inject one explicitly.
for _key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
    os.environ[_key] = ""

import pytest  # noqa: E402

from maestro.brains import SimulatedBrain  # noqa: E402
from maestro.engine import Engine  # noqa: E402


@pytest.fixture
def fast_engine() -> Engine:
    return Engine(brain_factory=lambda: SimulatedBrain(delay=0.0))

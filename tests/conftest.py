from __future__ import annotations

import os

# Make the offline brain instant so the whole suite runs fast.
os.environ["MAESTRO_SIM_DELAY"] = "0"

import pytest  # noqa: E402

from maestro.brains import SimulatedBrain  # noqa: E402
from maestro.engine import Engine  # noqa: E402


@pytest.fixture
def fast_engine() -> Engine:
    return Engine(brain_factory=lambda: SimulatedBrain(delay=0.0))

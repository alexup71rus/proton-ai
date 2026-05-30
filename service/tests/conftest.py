import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SERVICE_DIR = ROOT / "service"
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


@pytest.fixture(autouse=True)
def clear_public_proton_ai_env(monkeypatch):
    for name in (
        "PROTON_AI_ROUTER_LOG_FILE",
        "PROTON_AI_TRAIN_DEVICE",
        "PROTON_AI_TRAIN_STATE_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

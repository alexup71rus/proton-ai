from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web_backend.app import app  # noqa: E402


@pytest.fixture(autouse=True)
def clear_public_proton_ai_env(monkeypatch) -> None:
    for name in (
        "PROTON_AI_TOOLS_FILE",
        "PROTON_AI_DATASET_DIR",
        "PROTON_AI_ROUTER_LOG_FILE",
        "PROTON_AI_WORKSPACE_FILE",
        "PROTON_AI_SERVICE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

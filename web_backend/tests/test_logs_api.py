from __future__ import annotations

import json
from pathlib import Path

def test_get_logs_returns_human_friendly_rows(tmp_path: Path, monkeypatch, client) -> None:
    log_path = tmp_path / "router.jsonl"
    log_path.write_text(
        '{"user_text":"make it quieter","available_tools":["speaker","light"],"model_output":"{\\"tool_calls\\":[]}","validation_error":"unknown tool","final_action":"fallback"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PROTONX_ROUTER_LOG_FILE", str(log_path))

    response = client.get("/api/logs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["user"] == "make it quieter"
    assert payload["rows"][0]["result"] == "fallback"
    assert payload["rows"][0]["error"] == "unknown tool"


def test_post_logs_export_failed_cases_creates_dataset(tmp_path: Path, monkeypatch, client) -> None:
    log_path = tmp_path / "router.jsonl"
    log_path.write_text(
        '{"user_text":"make it quieter","available_tools":["light"],"model_output":"{\\"tool_calls\\":[]}","validation_error":"unknown tool","final_action":"fallback"}\n',
        encoding="utf-8",
    )
    tools_path = tmp_path / "tools.json"
    tools_path.write_text(
        json.dumps(
            [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["light"],
                    "arguments_schema": {"type": "object", "properties": {}, "required": []},
                    "executor_path": "web_backend/executors/get_current_time.py",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PROTONX_ROUTER_LOG_FILE", str(log_path))
    monkeypatch.setenv("PROTONX_TOOLS_FILE", str(tools_path))
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.post("/api/logs/export-failed-cases")

    assert response.status_code == 200
    payload = response.json()
    assert payload["exported"] is True
    assert payload["rows_written"] == 1
    assert payload["dataset"]["source"] == "logs_draft"
    assert (tmp_path / payload["dataset"]["name"]).exists()
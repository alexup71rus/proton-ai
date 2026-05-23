from __future__ import annotations

from pathlib import Path


def test_get_logs_returns_human_friendly_rows(tmp_path: Path, monkeypatch, client) -> None:
    log_path = tmp_path / "router.jsonl"
    log_path.write_text(
        '{"user_text":"make it quieter","candidate_tools":["speaker","light"],"model_output":"{\\"tool_calls\\":[]}","validation_error":"unknown tool","final_action":"fallback"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PROTONX_ROUTER_LOG_FILE", str(log_path))

    response = client.get("/api/logs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["user"] == "make it quieter"
    assert payload["rows"][0]["result"] == "fallback"
    assert payload["rows"][0]["error"] == "unknown tool"
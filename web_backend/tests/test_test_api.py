from __future__ import annotations

import web_backend.app as app_module


def test_post_test_returns_result_and_debug_sections(monkeypatch, client) -> None:
    monkeypatch.setattr(
        app_module,
        "load_tools",
        lambda: [
            {
                "name": "light",
                "description": "Light control",
                "tags": ["light"],
                "arguments_schema": {"type": "object", "properties": {}, "required": []},
            }
        ],
    )

    def fake_post_json(path: str, payload: dict) -> dict:
        if path == "/chat/completions":
            return {
                "tool_calls": [{"name": "light", "arguments": {"state": "on"}}],
                "answer": False,
            }
        if path == "/route/preview":
            return {
                "candidate_tools": ["light"],
                "model_output": "{}",
                "repaired_output": "{}",
                "validator_result": {"valid": True},
                "confidence": "high",
                "final_action": "tool_call",
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

    response = client.post("/api/test", json={"user_text": "turn on the lamp"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "tool_call"
    assert payload["result"]["tool_name"] == "light"
    assert payload["debug"]["confidence"] == "high"

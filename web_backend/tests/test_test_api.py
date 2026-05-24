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
                "executor_path": "executors/light.py",
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
    monkeypatch.setattr(
        app_module,
        "execute_tool",
        lambda tool, arguments: {
            "status": "executed",
            "tool_name": tool["name"],
            "output": {"state": arguments["state"]},
            "error": None,
        },
    )

    response = client.post("/api/test", json={"user_text": "turn on the lamp"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "tool_call"
    assert payload["result"]["tool_name"] == "light"
    assert payload["result"]["execution"] == {
        "status": "executed",
        "tool_name": "light",
        "output": {"state": "on"},
        "error": None,
    }
    assert payload["debug"]["confidence"] == "high"


def test_post_test_skips_execution_for_fallback(monkeypatch, client) -> None:
    monkeypatch.setattr(
        app_module,
        "load_tools",
        lambda: [
            {
                "name": "light",
                "description": "Light control",
                "tags": ["light"],
                "arguments_schema": {"type": "object", "properties": {}, "required": []},
                "executor_path": "executors/light.py",
            }
        ],
    )

    def fake_post_json(path: str, payload: dict) -> dict:
        if path == "/chat/completions":
            return {
                "tool_calls": [],
                "answer": False,
                "response": "fallback",
            }
        if path == "/route/preview":
            return {
                "candidate_tools": ["light"],
                "model_output": "{}",
                "repaired_output": "{}",
                "validator_result": {"valid": True},
                "confidence": "low",
                "final_action": "fallback",
            }
        raise AssertionError(f"Unexpected path: {path}")

    called: dict[str, bool] = {"value": False}

    def fake_execute_tool(tool, arguments):
        called["value"] = True
        return None

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)
    monkeypatch.setattr(app_module, "execute_tool", fake_execute_tool)

    response = client.post("/api/test", json={"user_text": "turn on the lamp"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "fallback"
    assert payload["result"]["execution"] is None
    assert called["value"] is False

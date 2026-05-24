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

    captured_payloads: dict[str, dict] = {}

    def fake_post_json(path: str, payload: dict) -> dict:
        captured_payloads[path] = payload
        if path == "/route/preview":
            return {
                "model_output": "{}",
                "repaired_output": "{}",
                "validator_result": {"valid": True},
                "final_action": "tool_call",
                "final_output": {
                    "tool_calls": [{"name": "light", "arguments": {"state": "on"}}],
                },
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)
    monkeypatch.setattr(
        app_module,
        "execute_tool",
        lambda tool, arguments: {
            "status": "executed",
            "tool_name": tool["name"],
            "output": {"state": arguments["state"], "response": "Light is on."},
            "error": None,
        },
    )

    response = client.post(
        "/api/test",
        json={
            "user_text": "turn on the lamp",
            "model_path": "/tmp/models/custom_router.pt",
            "tokenizer_path": "/tmp/models/custom_router.model",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "tool_call"
    assert payload["result"]["tool_name"] == "light"
    assert payload["result"]["execution"] == {
        "status": "executed",
        "tool_name": "light",
        "output": {"state": "on", "response": "Light is on."},
        "error": None,
    }
    assert payload["result"]["response"] == "Light is on."
    assert "/chat/completions" not in captured_payloads
    assert captured_payloads["/route/preview"]["model_path"] == "/tmp/models/custom_router.pt"
    assert captured_payloads["/route/preview"]["tokenizer_path"] == "/tmp/models/custom_router.model"


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

    def fake_post_json(path: str, _payload: dict) -> dict:
        if path == "/route/preview":
            return {
                "model_output": "{}",
                "repaired_output": "{}",
                "validator_result": {"valid": True},
                "final_action": "fallback",
                "final_output": {
                    "tool_calls": [{"name": "__fallback__", "arguments": {}}],
                },
            }
        raise AssertionError(f"Unexpected path: {path}")

    called: dict[str, bool] = {"value": False}

    def fake_execute_tool(_tool, _arguments):
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


def test_post_test_uses_workspace_model_paths(tmp_path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(tmp_path / "workspace.json"))
    (tmp_path / "workspace.json").write_text(
        """
{
  "selected_model": {
    "mode": "loaded",
    "label": "saved_router",
    "model_name": "tiny-router",
    "tokenizer_name": "sentencepiece-bpe",
    "output_root_dir": "data",
    "artifact_name": "saved_router",
    "model_path": "/tmp/saved_router.pt",
    "tokenizer_path": "/tmp/saved_router.model",
    "hidden_dim": 64,
    "num_layers": 2,
    "num_heads": 4
  },
  "training": {
    "dataset_name": "routing.jsonl",
    "epochs": 1,
    "batch_size": 1
    },
    "test": {
        "user_text": "turn on the lamp",
        "show_debug": false
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
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

    captured_payloads: dict[str, dict] = {}

    def fake_post_json(path: str, payload: dict) -> dict:
        captured_payloads[path] = payload
        if path == "/route/preview":
            return {
                "validator_result": {},
                "final_output": {"tool_calls": []},
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)
    monkeypatch.setattr(app_module, "execute_tool", lambda tool, arguments: None)

    response = client.post("/api/test", json={"user_text": "turn on the lamp"})

    assert response.status_code == 200
    assert "/chat/completions" not in captured_payloads
    assert captured_payloads["/route/preview"]["model_path"] == "/tmp/saved_router.pt"
    assert captured_payloads["/route/preview"]["tokenizer_path"] == "/tmp/saved_router.model"

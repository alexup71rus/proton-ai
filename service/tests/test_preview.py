from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from protonx.contracts import FALLBACK_TOOL_NAME
from protonx.routing import inference
from protonx.routing.model_runtime import ModelRuntime


client = TestClient(app)


def test_model_runtime_falls_back_when_weights_are_missing(tmp_path: Path):
    runtime = ModelRuntime(
        weights_path=tmp_path / "missing.pt",
        tokenizer_path=tmp_path / "missing.model",
    )
    result = runtime.generate(
        prompt={
            "tools": [{"name": "light", "arguments_schema": {"required": ["state"]}}],
            "user": "turn on the lamp",
        }
    )
    assert FALLBACK_TOOL_NAME in result


def test_route_preview_returns_full_pipeline_fields(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"light","arguments":{"state":"on"}}]}',
    )
    response = client.post(
        "/route/preview",
        json={
            "user_text": "turn on the lamp",
            "tools": [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["light", "lamp"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
                        "required": ["state"],
                    },
                }
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "tool_call"
    assert payload["final_output"] == {"tool_calls": [{"name": "light", "arguments": {"state": "on"}}]}
    assert payload["validation_error"] is None
    assert payload["serialized_prompt"].startswith("ИНСТРУМЕНТЫ:\n")
    assert "ПОЛЬЗОВАТЕЛЬ:\nturn on the lamp\nОТВЕТ:\n" in payload["serialized_prompt"]


def test_route_preview_uses_request_scoped_model_paths(monkeypatch, tmp_path):
    inference.MODEL_RUNTIME.weights_path = tmp_path / "default.pt"
    inference.MODEL_RUNTIME.tokenizer_path = tmp_path / "default.model"
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"light","arguments":{"state":"on"}}]}',
    )

    response = client.post(
        "/route/preview",
        json={
            "user_text": "turn on the lamp",
            "model_path": str(tmp_path / "weights" / "custom_router.pt"),
            "tokenizer_path": str(tmp_path / "tokenizers" / "custom_router.model"),
            "tools": [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["light", "lamp"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
                        "required": ["state"],
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    assert inference.MODEL_RUNTIME.weights_path == tmp_path / "weights" / "custom_router.pt"
    assert inference.MODEL_RUNTIME.tokenizer_path == tmp_path / "tokenizers" / "custom_router.model"


def test_route_preview_resolves_relative_model_paths_from_repo_root(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"light","arguments":{"state":"on"}}]}',
    )

    response = client.post(
        "/route/preview",
        json={
            "user_text": "turn on the lamp",
            "model_path": "data/weights/custom_router.pt",
            "tokenizer_path": "data/tokenizers/custom_router.model",
            "tools": [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["light", "lamp"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
                        "required": ["state"],
                    },
                }
            ],
        },
    )

    assert response.status_code == 200
    assert inference.MODEL_RUNTIME.weights_path == inference.ROOT_DIR / "data/weights/custom_router.pt"
    assert inference.MODEL_RUNTIME.tokenizer_path == inference.ROOT_DIR / "data/tokenizers/custom_router.model"


def test_route_preview_routes_single_zero_argument_tool_via_model(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"list_downloads","arguments":{}}]}',
    )
    response = client.post(
        "/route/preview",
        json={
            "user_text": "show me downloads",
            "tools": [
                {
                    "name": "list_downloads",
                    "description": "Downloads folder contents",
                    "tags": ["downloads", "download folder"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "tool_call"
    assert payload["final_output"] == {"tool_calls": [{"name": "list_downloads", "arguments": {}}]}
    assert payload["validation_error"] is None
    assert payload["serialized_prompt"].startswith("ИНСТРУМЕНТЫ:\n")
    assert payload["model_output"] == '{"tool_calls":[{"name":"list_downloads","arguments":{}}]}'


def test_route_preview_does_not_repair_invalid_model_json(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"list_downloads","arguments":{}}]',
    )
    response = client.post(
        "/route/preview",
        json={
            "user_text": "show me downloads",
            "tools": [
                {
                    "name": "list_downloads",
                    "description": "Downloads folder contents",
                    "tags": ["downloads", "download folder"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
            ],
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["model_output"] == '{"tool_calls":[{"name":"list_downloads","arguments":{}}]'
    assert payload["repaired_output"] is None
    assert payload["validator_result"] == {
        "valid": False,
        "error": "invalid json",
        "final_action": "fallback",
    }
    assert payload["final_output"] == {"tool_calls": [{"name": FALLBACK_TOOL_NAME, "arguments": {}}]}


def test_route_preview_routes_best_zero_argument_tool_via_model(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"get_node_version","arguments":{}}]}',
    )
    response = client.post(
        "/route/preview",
        json={
            "user_text": "show me node version",
            "tools": [
                {
                    "name": "get_node_version",
                    "description": "Node version",
                    "tags": ["node", "node version"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
                {
                    "name": "get_python_version",
                    "description": "Python version",
                    "tags": ["python", "python version"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "tool_call"
    assert payload["validation_error"] is None
    assert payload["serialized_prompt"].startswith("ИНСТРУМЕНТЫ:\n")
    assert payload["model_output"] == '{"tool_calls":[{"name":"get_node_version","arguments":{}}]}'


def test_route_preview_lets_model_route_ambiguous_text(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"__fallback__","arguments":{}}]}',
    )
    response = client.post(
        "/route/preview",
        json={
            "user_text": "lamp",
            "tools": [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["lamp"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
                        "required": ["state"],
                    },
                },
                {
                    "name": "night_light",
                    "description": "Night light control",
                    "tags": ["lamp"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
                        "required": ["state"],
                    },
                },
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "fallback"
    assert payload["final_output"] == {"tool_calls": [{"name": FALLBACK_TOOL_NAME, "arguments": {}}]}

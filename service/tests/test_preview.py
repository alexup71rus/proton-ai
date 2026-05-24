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
            "system": {"answer_allowed": False},
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
            "answer_allowed": False,
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
    assert payload["candidate_tools"] == ["light"]
    assert payload["confidence"] == "high"
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "tool_call"
    assert payload["validation_error"] is None
    assert payload["serialized_prompt"].startswith("TOOLS:\n")
    assert "USER:\nturn on the lamp\nOUTPUT:\n" in payload["serialized_prompt"]


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
            "answer_allowed": False,
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
            "answer_allowed": False,
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
    assert payload["candidate_tools"] == ["list_downloads"]
    assert payload["confidence"] == "high"
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "tool_call"
    assert payload["validation_error"] is None
    assert payload["serialized_prompt"].startswith("TOOLS:\n")
    assert payload["model_output"] == '{"tool_calls":[{"name":"list_downloads","arguments":{}}]}'


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
            "answer_allowed": False,
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
    assert payload["candidate_tools"] == ["get_node_version", "get_python_version"]
    assert payload["confidence"] == "high"
    assert payload["validator_result"]["valid"] is True
    assert payload["final_action"] == "tool_call"
    assert payload["validation_error"] is None
    assert payload["serialized_prompt"].startswith("TOOLS:\n")
    assert payload["model_output"] == '{"tool_calls":[{"name":"get_node_version","arguments":{}}]}'


def test_route_preview_falls_back_on_ambiguous_candidates_without_calling_model(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: (_ for _ in ()).throw(AssertionError("model should not run")),
    )
    response = client.post(
        "/route/preview",
        json={
            "user_text": "lamp",
            "answer_allowed": False,
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
    assert payload["confidence"] == "low"
    assert payload["validator_result"]["valid"] is False
    assert payload["final_action"] == "fallback"
    assert payload["candidate_tools"] == ["light", "night_light"]

from pathlib import Path

from fastapi.testclient import TestClient

from main import app
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
    assert '"fallback"' in result


def test_route_preview_returns_full_pipeline_fields(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"light","arguments":{"state":"on"}}],"answer":false}',
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

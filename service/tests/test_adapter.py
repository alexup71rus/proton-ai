from fastapi.testclient import TestClient

from main import app
from protonx.contracts import FALLBACK_TOOL_NAME
from protonx.routing import inference


client = TestClient(app)


def test_chat_completions_returns_openai_style_tool_call(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"light","arguments":{"state":"on"}}]}',
    )
    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "turn on the lamp"}],
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
            "tool_choice": "auto",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    tool_call = payload["tool_calls"][0]
    assert tool_call["id"].startswith("call_")
    assert tool_call["type"] == "function"
    assert tool_call["name"] == "light"
    assert tool_call["arguments"]["state"] == "on"


def test_chat_completions_returns_fallback_when_validator_rejects_model_output(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: '{"tool_calls":[{"name":"lamp","arguments":{"state":"on"}}]}',
    )
    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "turn on the lamp"}],
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
            "tool_choice": "auto",
            "answer_allowed": False,
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["tool_calls"] == []
    assert payload["fallback"] is True
    assert "response" not in payload


def test_chat_completions_returns_response_for_fallback_tool_when_answers_are_allowed(monkeypatch):
    monkeypatch.setattr(
        inference.MODEL_RUNTIME,
        "generate",
        lambda prompt: f'{{"tool_calls":[{{"name":"{FALLBACK_TOOL_NAME}","arguments":{{}}}}]}}',
    )

    response = client.post(
        "/chat/completions",
        json={
            "messages": [{"role": "user", "content": "tell me a joke"}],
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
            "tool_choice": "auto",
            "answer_allowed": True,
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["tool_calls"] == []
    assert payload["fallback"] is True
    assert payload["response"] == "Я работаю только с доступными инструментами."

from __future__ import annotations

import json
from pathlib import Path

import web_backend.app as app_module


def _sample_tool() -> dict:
    return {
        "name": "light",
        "description": "Light control",
        "tags": ["light", "lamp"],
        "arguments_schema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["on", "off"],
                }
            },
            "required": ["state"],
        },
    }


def test_get_tools_reads_registry_file(tmp_path: Path, monkeypatch, client) -> None:
    registry_path = tmp_path / "tools.json"
    registry_path.write_text(json.dumps([_sample_tool()]), encoding="utf-8")
    monkeypatch.setenv("PROTONX_TOOLS_FILE", str(registry_path))

    response = client.get("/api/tools")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tools"][0]["name"] == "light"
    assert payload["source"]["name"] == "tools.json"


def test_put_tools_saves_registry_file(tmp_path: Path, monkeypatch, client) -> None:
    registry_path = tmp_path / "tools.json"
    monkeypatch.setenv("PROTONX_TOOLS_FILE", str(registry_path))

    response = client.put("/api/tools", json={"tools": [_sample_tool()]})

    assert response.status_code == 200
    assert registry_path.exists()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert payload[0]["name"] == "light"


def test_post_tools_validate_forwards_to_service(monkeypatch, client) -> None:
    captured: dict[str, object] = {}

    def fake_post_json(path: str, payload: dict) -> dict:
        captured["path"] = path
        captured["payload"] = payload
        return {"valid": True, "tool_count": len(payload["tools"])}

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

    response = client.post("/api/tools/validate", json={"tools": [_sample_tool()]})

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert captured["path"] == "/tools/validate"
    assert captured["payload"] == {"tools": [_sample_tool()]}
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_endpoint_still_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_route_preview_requires_user_text_and_tools():
    response = client.post("/route/preview", json={})
    assert response.status_code == 422


def test_tools_validate_accepts_valid_registry():
    response = client.post(
        "/tools/validate",
        json={
            "tools": [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["light", "lamp"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {
                            "state": {"type": "string", "enum": ["on", "off"]}
                        },
                        "required": ["state"],
                    },
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_tools_validate_rejects_unsupported_schema_subset():
    response = client.post(
        "/tools/validate",
        json={
            "tools": [
                {
                    "name": "thermostat",
                    "description": "Temperature control",
                    "tags": ["temperature"],
                    "arguments_schema": {
                        "type": "object",
                        "properties": {
                            "degrees": {"type": "integer"}
                        },
                        "required": ["degrees"],
                    },
                }
            ]
        },
    )
    assert response.status_code == 400

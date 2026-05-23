from __future__ import annotations

import json
from pathlib import Path

import web_backend.app as app_module


def test_get_datasets_lists_known_jsonl_files(tmp_path: Path, monkeypatch, client) -> None:
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text('{"x":1}\n', encoding="utf-8")
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.get("/api/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["datasets"][0]["name"] == "routing.jsonl"


def test_post_dataset_import_saves_uploaded_file(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.post(
        "/api/datasets/import",
        files={"file": ("routing.jsonl", b'{"x":1}\n', "application/json")},
    )

    assert response.status_code == 200
    assert (tmp_path / "routing.jsonl").exists()
    assert response.json()["dataset"]["name"] == "routing.jsonl"


def test_post_dataset_generate_calls_service(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    tools_path = tmp_path / "tools.json"
    tools_path.write_text(
        json.dumps(
            [
                {
                    "name": "light",
                    "description": "Light control",
                    "tags": ["light"],
                    "arguments_schema": {"type": "object", "properties": {}, "required": []},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PROTONX_TOOLS_FILE", str(tools_path))

    generated_path = tmp_path / "routing.jsonl"
    captured: dict[str, object] = {}

    def fake_post_json(path: str, payload: dict) -> dict:
        captured["path"] = path
        captured["payload"] = payload
        generated_path.write_text('{"row":1}\n', encoding="utf-8")
        return {"rows_written": 1, "output_path": str(generated_path)}

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

    response = client.post("/api/datasets/generate")

    assert response.status_code == 200
    assert response.json()["generated"] is True
    assert captured["path"] == "/train/dataset/build"

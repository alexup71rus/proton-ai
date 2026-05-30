from __future__ import annotations

import json
from pathlib import Path

import web_backend.app as app_module


def _valid_dataset_line() -> bytes:
    row = {
        "tools": [
            {
                "name": "light",
                "tags": ["light"],
            }
        ],
        "user": "show me light",
        "assistant": {
            "tool_calls": [{"name": "light", "arguments": {}}],
        },
    }
    return (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")


def test_get_datasets_lists_known_jsonl_files(tmp_path: Path, monkeypatch, client) -> None:
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_bytes(_valid_dataset_line())
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.get("/api/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_dir"] == str(tmp_path)
    assert payload["datasets"][0]["name"] == "routing.jsonl"
    assert payload["datasets"][0]["row_count"] == 1
    assert payload["datasets"][0]["validation_status"] == "valid"


def test_get_datasets_uses_workspace_dataset_dir(tmp_path: Path, monkeypatch, client) -> None:
    dataset_dir = tmp_path / "selected"
    dataset_dir.mkdir()
    (dataset_dir / "routing.jsonl").write_bytes(_valid_dataset_line())
    workspace_path = tmp_path / "workspace.json"
    workspace_path.write_text(
        json.dumps(
            {
                "training": {
                    "dataset_dir": str(dataset_dir),
                    "dataset_name": "routing.jsonl",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("PROTONX_DATASET_DIR", raising=False)
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(workspace_path))

    response = client.get("/api/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_dir"] == str(dataset_dir)
    assert payload["datasets"][0]["name"] == "routing.jsonl"


def test_post_dataset_import_saves_uploaded_file(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.post(
        "/api/datasets/import",
        files={"file": ("routing.jsonl", _valid_dataset_line(), "application/json")},
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
        generated_path.write_bytes(_valid_dataset_line())
        return {"rows_written": 1, "output_path": str(generated_path)}

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

    response = client.post("/api/datasets/generate")

    assert response.status_code == 200
    assert response.json()["bootstrapped"] is True
    assert captured["path"] == "/train/dataset/build"


def test_post_dataset_import_rejects_invalid_jsonl(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.post(
        "/api/datasets/import",
        files={"file": ("broken.jsonl", b'{"x":1}\n', "application/json")},
    )

    assert response.status_code == 400
    assert "compact fields" in response.json()["detail"]


def test_post_dataset_import_rejects_assistant_extra_fields(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.post(
        "/api/datasets/import",
        files={
            "file": (
                "broken.jsonl",
                (
                    '{"tools":[{"name":"light","tags":["light"]}],"user":"show me light",'
                    '"assistant":{"tool_calls":[{"name":"light","arguments":{}}],"answer":false}}\n'
                ).encode("utf-8"),
                "application/json",
            )
        },
    )

    assert response.status_code == 400
    assert "only contain tool_calls" in response.json()["detail"]


def test_get_dataset_preview_returns_preview_and_validation(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_bytes(_valid_dataset_line())

    response = client.get("/api/datasets/routing.jsonl/preview?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["name"] == "routing.jsonl"
    assert payload["validation"]["status"] == "valid"
    assert payload["preview_lines"][0]["line_number"] == 1


def test_post_dataset_manual_creates_manual_asset(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))

    response = client.post(
        "/api/datasets/manual",
        json={
            "dataset_name": "manual-set",
            "content": _valid_dataset_line().decode("utf-8"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["source"] == "manual"
    assert (tmp_path / "manual-set.jsonl").exists()


def test_post_dataset_duplicate_and_delete_manage_asset_files(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_bytes(_valid_dataset_line())

    duplicate_response = client.post("/api/datasets/routing.jsonl/duplicate")

    assert duplicate_response.status_code == 200
    duplicate_name = duplicate_response.json()["dataset"]["name"]
    assert (tmp_path / duplicate_name).exists()

    delete_response = client.delete(f"/api/datasets/{duplicate_name}")

    assert delete_response.status_code == 200
    assert not (tmp_path / duplicate_name).exists()


def test_post_dataset_append_validates_and_updates_row_count(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_bytes(_valid_dataset_line())

    response = client.post(
        "/api/datasets/routing.jsonl/append",
        json={"content": _valid_dataset_line().decode("utf-8").strip()},
    )

    assert response.status_code == 200
    assert response.json()["dataset"]["row_count"] == 2

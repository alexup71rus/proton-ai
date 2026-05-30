from __future__ import annotations

from pathlib import Path

import web_backend.app as app_module


def _valid_dataset_line() -> str:
    return (
        '{"tools":[{"name":"light","tags":["light"]}],'
        '"user":"show me light",'
        '"assistant":{"tool_calls":[{"name":"light","arguments":{}}]}}'
        '\n'
    )


def test_get_training_status_returns_ui_friendly_shape(monkeypatch, client) -> None:
    monkeypatch.setattr(
        app_module.service_client,
        "get_json",
        lambda path: {
            "status": "idle",
        },
    )

    response = client.get("/api/training/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "idle"
    assert payload["loss_history"] == []
    assert payload["metrics"] == {}
    assert payload["error"] is None
    assert payload["current_epoch"] == 0
    assert payload["batch_size"] == 1
    assert payload["dataset_path"] is None
    assert payload["dataset_row_count"] == 0
    assert payload["eval_total"] == 0
    assert payload["eval_exact"] == 0


def test_get_training_status_downsamples_large_loss_history(monkeypatch, client) -> None:
    monkeypatch.setattr(
        app_module.service_client,
        "get_json",
        lambda path: {
            "status": "running",
            "loss_history": list(range(2500)),
        },
    )

    response = client.get("/api/training/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["loss_history_total"] == 2500
    assert len(payload["loss_history"]) == 500


def test_post_training_start_forwards_config(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(tmp_path / "workspace.json"))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text(_valid_dataset_line(), encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_post_json(path: str, payload: dict) -> dict:
        captured["path"] = path
        captured["payload"] = payload
        return {"status": "running"}

    monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

    response = client.post(
        "/api/training/start",
        json={
            "dataset_name": "routing.jsonl",
            "epochs": 2,
            "batch_size": 4,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
            "output_root_dir": "data",
            "artifact_name": "custom_router",
            "hidden_dim": 32,
            "num_layers": 1,
            "num_heads": 4,
        },
    )

    assert response.status_code == 200
    assert captured["path"] == "/train/start"
    assert captured["payload"] == {
        "dataset_path": str(dataset_path),
        "epochs": 2,
        "batch_size": 4,
        "model_name": "tiny-router",
        "tokenizer_name": "sentencepiece-bpe",
        "output_root_dir": "data",
        "artifact_name": "custom_router",
        "resume_model_path": None,
        "resume_tokenizer_path": None,
        "hidden_dim": 32,
        "num_layers": 1,
        "num_heads": 4,
        "learning_rate": 0.001,
    }


def test_post_training_start_normalizes_partial_service_payload(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(tmp_path / "workspace.json"))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text(_valid_dataset_line(), encoding="utf-8")

    monkeypatch.setattr(
        app_module.service_client,
        "post_json",
        lambda path, payload: {"status": "running", "current_epoch": 1},
    )

    response = client.post(
        "/api/training/start",
        json={
            "dataset_name": "routing.jsonl",
            "epochs": 2,
            "batch_size": 4,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
            "output_root_dir": "data",
            "artifact_name": "custom_router",
            "hidden_dim": 32,
            "num_layers": 1,
            "num_heads": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["current_epoch"] == 1
    assert payload["loss_history"] == []
    assert payload["metrics"] == {}
    assert payload["dataset_path"] is None
    assert payload["dataset_row_count"] == 0
    assert payload["eval_total"] == 0
    assert payload["output_root_dir"] is None
    assert payload["artifact_name"] == "router"


def test_post_training_start_rejects_invalid_dataset(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text('{"x":1}\n', encoding="utf-8")

    response = client.post(
        "/api/training/start",
        json={
            "dataset_name": "routing.jsonl",
            "epochs": 1,
            "batch_size": 1,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
            "output_root_dir": "data",
            "artifact_name": "broken_router",
            "hidden_dim": 64,
            "num_layers": 2,
            "num_heads": 4,
        },
    )

    assert response.status_code == 400
    assert "Dataset validation failed" in response.json()["detail"]


def test_post_training_start_rejects_existing_new_artifact(tmp_path: Path, monkeypatch, client) -> None:
    monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(tmp_path / "workspace.json"))
    output_root = tmp_path / "artifacts"
    weights_dir = output_root / "weights"
    weights_dir.mkdir(parents=True)
    (weights_dir / "custom_router.pt").write_bytes(b"existing")

    def fail_post_json(path: str, payload: dict) -> dict:
        raise AssertionError("training service should not be called for an existing artifact")

    monkeypatch.setattr(app_module.service_client, "post_json", fail_post_json)

    response = client.post(
        "/api/training/start",
        json={
            "dataset_name": "routing.jsonl",
            "epochs": 2,
            "batch_size": 4,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
            "output_root_dir": str(output_root),
            "artifact_name": "custom_router",
            "hidden_dim": 32,
            "num_layers": 1,
            "num_heads": 4,
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_post_training_start_uses_workspace_defaults(tmp_path: Path, monkeypatch, client) -> None:
        monkeypatch.setenv("PROTONX_DATASET_DIR", str(tmp_path))
        monkeypatch.setenv("PROTONX_WORKSPACE_FILE", str(tmp_path / "workspace.json"))
        dataset_path = tmp_path / "custom.jsonl"
        dataset_path.write_text(_valid_dataset_line(), encoding="utf-8")
        (tmp_path / "workspace.json").write_text(
                """
{
    "selected_model": {
        "mode": "loaded",
        "label": "saved_router",
        "model_name": "tiny-router",
        "tokenizer_name": "sentencepiece-bpe",
        "output_root_dir": "data/models",
        "artifact_name": "saved_router",
        "model_path": "/tmp/saved_router.pt",
        "tokenizer_path": "/tmp/saved_router.model",
        "hidden_dim": 96,
        "num_layers": 3,
        "num_heads": 8
    },
    "training": {
        "dataset_name": "custom.jsonl",
        "epochs": 5,
        "batch_size": 2
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
        )
        captured: dict[str, object] = {}

        def fake_post_json(path: str, payload: dict) -> dict:
                captured["path"] = path
                captured["payload"] = payload
                return {"status": "running"}

        monkeypatch.setattr(app_module.service_client, "post_json", fake_post_json)

        response = client.post("/api/training/start", json={})

        assert response.status_code == 200
        assert captured["path"] == "/train/start"
        assert captured["payload"] == {
                "dataset_path": str(dataset_path),
                "epochs": 5,
                "batch_size": 2,
                "model_name": "tiny-router",
                "tokenizer_name": "sentencepiece-bpe",
                "output_root_dir": "data/models",
                "artifact_name": "saved_router",
                "resume_model_path": "/tmp/saved_router.pt",
                "resume_tokenizer_path": "/tmp/saved_router.model",
                "hidden_dim": 96,
                "num_layers": 3,
                "num_heads": 8,
                    "learning_rate": 0.001,
        }

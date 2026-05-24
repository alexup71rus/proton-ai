import time
from pathlib import Path

import torch

from fastapi.testclient import TestClient

from main import app
from protonx.training.state import TRAINING_STATE


client = TestClient(app)


def test_train_status_returns_idle_state_before_training():
    TRAINING_STATE.reset()
    response = client.get("/train/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "idle"
    assert payload["current_epoch"] == 0
    assert payload["loss_history"] == []
    assert payload["metrics"] == {}
    assert payload["error"] is None


def test_train_status_exposes_failed_state_details():
    TRAINING_STATE.reset()
    TRAINING_STATE.status = "failed"
    TRAINING_STATE.error = "training exploded"

    response = client.get("/train/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error"] == "training exploded"


def test_train_start_accepts_config_and_eventually_completes(tmp_path):
    TRAINING_STATE.reset()
    dataset_path = tmp_path / "routing.jsonl"
    output_root_dir = tmp_path / "artifacts"
    dataset_path.write_text(
        '{"tools":[{"name":"__fallback__","tags":["fallback"]}],"user":"turn on the lamp","assistant":{"tool_calls":[{"name":"__fallback__","arguments":{}}]}}\n',
        encoding="utf-8",
    )
    response = client.post(
        "/train/start",
        json={
            "dataset_path": str(dataset_path),
            "epochs": 1,
            "batch_size": 1,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
            "output_root_dir": str(output_root_dir),
            "artifact_name": "custom_router",
            "hidden_dim": 32,
            "num_layers": 1,
            "num_heads": 4,
        },
    )
    assert response.status_code == 200
    start_payload = response.json()
    assert start_payload["status"] in {"running", "completed"}
    assert start_payload["total_epochs"] == 1
    assert start_payload["batch_size"] == 1

    final_payload = start_payload
    for _ in range(50):
        final_payload = client.get("/train/status").json()
        if final_payload["status"] == "completed":
            break
        time.sleep(0.05)

    assert final_payload["status"] == "completed"
    assert final_payload["tokenizer_path"].endswith("/tokenizers/custom_router.model")
    assert final_payload["model_name"] == "tiny-router"
    assert isinstance(final_payload["loss_history"], list)
    assert final_payload["dataset_path"] == str(dataset_path)
    assert final_payload["dataset_row_count"] == 1
    assert len(final_payload["dataset_sha1"]) == 40
    assert final_payload["output_root_dir"] == str(output_root_dir)
    assert final_payload["artifact_name"] == "custom_router"
    assert final_payload["eval_total"] >= 1
    assert final_payload["eval_fallback_total"] == final_payload["eval_total"]
    assert final_payload["model_path"].endswith("/weights/custom_router.pt")

    checkpoint = torch.load(Path(final_payload["model_path"]), map_location="cpu")
    assert checkpoint["config"]["hidden_dim"] == 32
    assert checkpoint["config"]["num_layers"] == 1
    assert checkpoint["output_format"] == "json-v1"
    assert checkpoint["evaluation"]["mode"] == "unique_holdout"
    assert checkpoint["evaluation"]["eval_total"] == final_payload["eval_total"]


def test_train_start_rejects_invalid_dataset_before_training(tmp_path):
    TRAINING_STATE.reset()
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text(
        '{"tools":[{"name":"light","tags":["light"]}],"user":"turn on the lamp","assistant":{"tool_calls":[{"name":"lamp","arguments":{}}]}}\n',
        encoding="utf-8",
    )

    response = client.post(
        "/train/start",
        json={
            "dataset_path": str(dataset_path),
            "epochs": 1,
            "batch_size": 1,
            "model_name": "tiny-router",
            "tokenizer_name": "sentencepiece-bpe",
            "output_root_dir": str(tmp_path / "artifacts"),
            "artifact_name": "broken_router",
        },
    )

    assert response.status_code == 400
    assert "Dataset validation failed" in response.json()["detail"]

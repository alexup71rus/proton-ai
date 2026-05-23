from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_train_status_returns_idle_state_before_training():
    response = client.get("/train/status")
    assert response.status_code == 200
    assert response.json()["status"] == "idle"


def test_train_start_returns_completed_state_with_tokenizer_path(tmp_path):
    dataset_path = tmp_path / "routing.jsonl"
    dataset_path.write_text(
        '{"system":{"answer_allowed":false,"fallback_message":"fallback"},"tools":[],"messages":[{"role":"user","content":"turn on the lamp"},{"role":"assistant","content":"{\\"tool_calls\\":[],\\"answer\\":true,\\"response\\":\\"fallback\\",\\"fallback\\":true}"}]}\n',
        encoding="utf-8",
    )
    response = client.post("/train/start", json={"dataset_path": str(dataset_path)})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["tokenizer_path"].endswith(".model")

import json

from protonx.logging import append_router_log


def test_router_log_uses_public_env_name(tmp_path, monkeypatch):
    legacy_path = tmp_path / "legacy.jsonl"
    public_path = tmp_path / "public.jsonl"
    monkeypatch.setenv("PROTONX_ROUTER_LOG_FILE", str(legacy_path))
    monkeypatch.setenv("PROTON_AI_ROUTER_LOG_FILE", str(public_path))

    append_router_log({"user_text": "hello"})

    assert public_path.exists()
    assert not legacy_path.exists()
    payload = json.loads(public_path.read_text(encoding="utf-8"))
    assert payload["user_text"] == "hello"
    assert payload["created_at"]

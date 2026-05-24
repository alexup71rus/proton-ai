from protonx.routing.model_runtime import ModelRuntime
from protonx.training.model import TinyRouterConfig


def test_get_runtime_caches_loaded_artifacts(monkeypatch, tmp_path):
    runtime = ModelRuntime(
        weights_path=tmp_path / "tiny_router_v1.pt",
        tokenizer_path=tmp_path / "routing_spm.model",
    )

    monkeypatch.setattr(runtime, "_artifacts_signature", lambda: (1, 2, 3, 4))
    load_calls: list[int] = []
    fake_runtime = (TinyRouterConfig(16, 8, 1, 1, 32), object(), object())

    def fake_loader():
        load_calls.append(1)
        return fake_runtime

    monkeypatch.setattr(runtime, "_load_runtime_artifacts", fake_loader)

    assert runtime._get_runtime() == fake_runtime
    assert runtime._get_runtime() == fake_runtime
    assert len(load_calls) == 1


def test_get_runtime_reloads_when_artifacts_change(monkeypatch, tmp_path):
    runtime = ModelRuntime(
        weights_path=tmp_path / "tiny_router_v1.pt",
        tokenizer_path=tmp_path / "routing_spm.model",
    )

    signatures = iter([(1, 2, 3, 4), (5, 6, 7, 8)])
    monkeypatch.setattr(runtime, "_artifacts_signature", lambda: next(signatures))
    load_calls: list[int] = []

    def fake_loader():
        load_calls.append(1)
        return (TinyRouterConfig(16, 8, 1, 1, 32), object(), object())

    monkeypatch.setattr(runtime, "_load_runtime_artifacts", fake_loader)

    runtime._get_runtime()
    runtime._get_runtime()

    assert len(load_calls) == 2
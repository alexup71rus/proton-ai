import json
import os
from dataclasses import MISSING, asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from protonx.config import DATA_DIR


MAX_PUBLIC_LOSS_HISTORY_POINTS = 500


def _field_default_value(state_field) -> Any:
    if state_field.default_factory is not MISSING:
        return state_field.default_factory()
    if state_field.default is not MISSING:
        return state_field.default
    raise ValueError(f"TrainingState field has no default: {state_field.name}")


def downsample_loss_history(values: list[float], max_points: int = MAX_PUBLIC_LOSS_HISTORY_POINTS) -> list[float]:
    if max_points <= 0 or len(values) <= max_points:
        return list(values)

    bin_size = len(values) / max_points
    sampled: list[float] = []
    for index in range(max_points):
        start = int(index * bin_size)
        end = int((index + 1) * bin_size)
        if index == max_points - 1:
            end = len(values)
        end = max(end, start + 1)
        window = values[start:end]
        sampled.append(sum(window) / len(window))
    return sampled


def public_training_state_payload(state: dict[str, Any]) -> dict[str, Any]:
    payload = dict(state)
    raw_history = payload.get("loss_history")
    if not isinstance(raw_history, list):
        raw_history = []
    loss_history = [float(value) for value in raw_history if isinstance(value, (int, float))]
    payload["loss_history_total"] = len(loss_history)
    payload["loss_history"] = downsample_loss_history(loss_history)
    return payload


@dataclass
class TrainingState:
    status: str = "idle"
    current_epoch: int = 0
    total_epochs: int = 0
    current_step: int = 0
    total_steps: int = 0
    loss: float | None = None
    loss_history: list[float] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    batch_size: int = 1
    model_name: str = "tiny-router"
    tokenizer_name: str = "sentencepiece-bpe"
    output_root_dir: str | None = None
    artifact_name: str = "tiny_router_v1"
    checkpoint_path: str | None = None
    model_path: str | None = None
    tokenizer_path: str | None = None
    dataset_path: str | None = None
    dataset_sha1: str | None = None
    dataset_row_count: int = 0
    process_id: int | None = None
    eval_total: int = 0
    eval_valid: int = 0
    eval_exact: int = 0
    eval_positive_total: int = 0
    eval_positive_exact: int = 0
    eval_fallback_total: int = 0
    eval_fallback_exact: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def update(self, **values: Any) -> None:
        for name, value in values.items():
            setattr(self, name, value)

    def reset(self) -> None:
        self.update(**{state_field.name: _field_default_value(state_field) for state_field in fields(self)})

    def begin_run(
        self,
        *,
        total_epochs: int,
        total_steps: int,
        batch_size: int,
        model_name: str,
        tokenizer_name: str,
        output_root_dir: str,
        artifact_name: str,
        dataset_path: str,
        dataset_sha1: str,
        dataset_row_count: int,
    ) -> None:
        self.reset()
        self.update(
            status="running",
            total_epochs=total_epochs,
            total_steps=total_steps,
            batch_size=batch_size,
            model_name=model_name,
            tokenizer_name=tokenizer_name,
            output_root_dir=output_root_dir,
            artifact_name=artifact_name,
            dataset_path=dataset_path,
            dataset_sha1=dataset_sha1,
            dataset_row_count=dataset_row_count,
        )

    def apply_evaluation_summary(self, summary: dict[str, int] | None) -> None:
        values = summary or {}
        self.update(
            eval_total=values.get("eval_total", 0),
            eval_valid=values.get("eval_valid", 0),
            eval_exact=values.get("eval_exact", 0),
            eval_positive_total=values.get("eval_positive_total", 0),
            eval_positive_exact=values.get("eval_positive_exact", 0),
            eval_fallback_total=values.get("eval_fallback_total", 0),
            eval_fallback_exact=values.get("eval_fallback_exact", 0),
        )


TRAINING_STATE = TrainingState()


def training_state_path() -> Path:
    raw_path = os.getenv("PROTONX_TRAIN_STATE_PATH")
    if raw_path:
        return Path(raw_path).expanduser()
    return DATA_DIR / "workspace" / "training_state.json"


def write_training_state(state: TrainingState = TRAINING_STATE) -> dict:
    payload = state.to_dict()
    path = training_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def read_training_state() -> dict:
    path = training_state_path()
    if not path.exists():
        return TRAINING_STATE.to_dict()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return TRAINING_STATE.to_dict()
    if not isinstance(payload, dict):
        return TRAINING_STATE.to_dict()
    return payload

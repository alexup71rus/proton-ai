from dataclasses import MISSING, asdict, dataclass, field, fields
from typing import Any


def _field_default_value(state_field) -> Any:
    if state_field.default_factory is not MISSING:
        return state_field.default_factory()
    if state_field.default is not MISSING:
        return state_field.default
    raise ValueError(f"TrainingState field has no default: {state_field.name}")


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

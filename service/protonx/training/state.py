from dataclasses import asdict, dataclass


@dataclass
class TrainingState:
    status: str = "idle"
    current_step: int = 0
    total_steps: int = 0
    loss: float | None = None
    model_path: str | None = None
    tokenizer_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


TRAINING_STATE = TrainingState()

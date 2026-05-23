from dataclasses import asdict, dataclass, field


@dataclass
class TrainingState:
    status: str = "idle"
    current_epoch: int = 0
    total_epochs: int = 0
    current_step: int = 0
    total_steps: int = 0
    loss: float | None = None
    loss_history: list[float] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    error: str | None = None
    batch_size: int = 1
    model_name: str = "tiny-router"
    tokenizer_name: str = "sentencepiece-bpe"
    checkpoint_path: str | None = None
    model_path: str | None = None
    tokenizer_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def reset(self) -> None:
        self.status = "idle"
        self.current_epoch = 0
        self.total_epochs = 0
        self.current_step = 0
        self.total_steps = 0
        self.loss = None
        self.loss_history = []
        self.metrics = {}
        self.error = None
        self.batch_size = 1
        self.model_name = "tiny-router"
        self.tokenizer_name = "sentencepiece-bpe"
        self.checkpoint_path = None
        self.model_path = None
        self.tokenizer_path = None


TRAINING_STATE = TrainingState()

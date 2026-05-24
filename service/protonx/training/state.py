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
        self.output_root_dir = None
        self.artifact_name = "tiny_router_v1"
        self.checkpoint_path = None
        self.model_path = None
        self.tokenizer_path = None
        self.dataset_path = None
        self.dataset_sha1 = None
        self.dataset_row_count = 0
        self.eval_total = 0
        self.eval_valid = 0
        self.eval_exact = 0
        self.eval_positive_total = 0
        self.eval_positive_exact = 0
        self.eval_fallback_total = 0
        self.eval_fallback_exact = 0


TRAINING_STATE = TrainingState()

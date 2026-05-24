from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


def _default_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {},
        "required": [],
    }


def _coalesce_training_status_value(value: Any, fallback: Any) -> Any:
    if fallback is None:
        return value
    if isinstance(fallback, int):
        return fallback if value is None else value
    return value or fallback


class ToolDefinition(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    arguments_schema: dict[str, Any] = Field(default_factory=_default_schema)
    executor_path: str = ""


class ToolsPayload(BaseModel):
    tools: list[ToolDefinition] = Field(default_factory=list)


class ToolsSource(BaseModel):
    name: str
    path: str


class ToolsResponse(BaseModel):
    tools: list[ToolDefinition] = Field(default_factory=list)
    source: ToolsSource


class SaveToolsResponse(ToolsResponse):
    saved: bool = True


class ToolsValidationResponse(BaseModel):
    valid: bool
    tool_count: int


class DatasetSummary(BaseModel):
    name: str
    size_bytes: int
    updated_at: str
    sha1: str
    row_count: int = 0
    validation_status: Literal["valid", "invalid"] = "invalid"
    issue_count: int = 0
    source: Literal["imported", "tools_bootstrap", "manual", "logs_draft"] = "imported"


class DatasetsResponse(BaseModel):
    datasets: list[DatasetSummary] = Field(default_factory=list)


class DatasetValidationIssue(BaseModel):
    line_number: int
    message: str


class DatasetValidationReport(BaseModel):
    status: Literal["valid", "invalid"] = "invalid"
    row_count: int = 0
    issue_count: int = 0
    issues: list[DatasetValidationIssue] = Field(default_factory=list)


class DatasetPreviewLine(BaseModel):
    line_number: int
    raw: str


class DatasetDetailResponse(BaseModel):
    dataset: DatasetSummary
    preview_lines: list[DatasetPreviewLine] = Field(default_factory=list)
    validation: DatasetValidationReport


class ImportDatasetResponse(BaseModel):
    imported: bool = True
    dataset: DatasetSummary


class DatasetBootstrapPayload(BaseModel):
    dataset_name: str = "routing.jsonl"


class DatasetCreatePayload(BaseModel):
    dataset_name: str
    content: str


class DatasetAppendPayload(BaseModel):
    content: str


class DatasetMutationResponse(BaseModel):
    saved: bool = True
    dataset: DatasetSummary


class DatasetDuplicateResponse(BaseModel):
    duplicated: bool = True
    dataset: DatasetSummary


class DatasetDeleteResponse(BaseModel):
    deleted: bool = True
    name: str


class DatasetBootstrapResponse(BaseModel):
    bootstrapped: bool = True
    rows_written: int
    dataset: DatasetSummary


class LogsExportResponse(BaseModel):
    exported: bool = True
    rows_written: int
    dataset: DatasetSummary


class WorkspaceModelSettings(BaseModel):
    mode: Literal["new", "loaded"] = "new"
    label: str = "tiny_router_v1"
    model_name: str = "tiny-router"
    tokenizer_name: str = "sentencepiece-bpe"
    output_root_dir: str = "data"
    artifact_name: str = "tiny_router_v1"
    model_path: str | None = None
    tokenizer_path: str | None = None
    hidden_dim: int = 64
    num_layers: int = 2
    num_heads: int = 4


class WorkspaceTrainingSettings(BaseModel):
    dataset_name: str = "routing.jsonl"
    epochs: int = 1
    batch_size: int = 1
    learning_rate: float = 1e-3


class WorkspaceTestSettings(BaseModel):
    user_text: str = "сделай свет потеплее"
    show_debug: bool = False


class WorkspaceSettingsPayload(BaseModel):
    selected_model: WorkspaceModelSettings = Field(default_factory=WorkspaceModelSettings)
    training: WorkspaceTrainingSettings = Field(default_factory=WorkspaceTrainingSettings)
    test: WorkspaceTestSettings = Field(default_factory=WorkspaceTestSettings)


class WorkspaceSettingsResponse(WorkspaceSettingsPayload):
    storage_path: str


class TrainingStartPayload(BaseModel):
    dataset_name: str | None = None
    epochs: int | None = None
    batch_size: int | None = None
    model_name: str | None = None
    tokenizer_name: str | None = None
    output_root_dir: str | None = None
    artifact_name: str | None = None
    resume_model_path: str | None = None
    resume_tokenizer_path: str | None = None
    hidden_dim: int | None = None
    num_layers: int | None = None
    num_heads: int | None = None
    learning_rate: float | None = None


class TrainingStatusResponse(BaseModel):
    status: str = "idle"
    current_epoch: int = 0
    total_epochs: int = 0
    current_step: int = 0
    total_steps: int = 0
    loss: float | None = None
    loss_history: list[float] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
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

    @classmethod
    def from_service_payload(cls, payload: dict[str, Any] | None) -> "TrainingStatusResponse":
        raw = payload or {}
        defaults = cls().model_dump()
        normalized = {
            field_name: _coalesce_training_status_value(raw.get(field_name), fallback)
            for field_name, fallback in defaults.items()
        }
        return cls.model_validate(normalized)


class TestPayload(BaseModel):
    user_text: str
    model_path: str | None = None
    tokenizer_path: str | None = None


class ModelImportResponse(BaseModel):
    imported: bool = True
    output_root_dir: str
    artifact_name: str
    model_path: str
    tokenizer_path: str


class ToolExecutionPayload(BaseModel):
    status: str
    tool_name: str | None = None
    output: Any | None = None
    error: str | None = None


class TestResultPayload(BaseModel):
    status: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    response: str | None = None
    validation_error: str | None = None
    execution: ToolExecutionPayload | None = None


class TestDebugPayload(BaseModel):
    serialized_prompt: str = ""
    raw_model_output: str = ""
    validation_error: str | None = None
    repaired_output: str | None = None
    validator_result: dict[str, Any] = Field(default_factory=dict)
    final_action: str = "fallback"


class TestResponse(BaseModel):
    result: TestResultPayload
    debug: TestDebugPayload


class LogRow(BaseModel):
    user: str
    candidates: list[str] = Field(default_factory=list)
    raw_output_summary: str
    raw_output: str = ""
    error: str
    result: str


class LogsResponse(BaseModel):
    rows: list[LogRow] = Field(default_factory=list)

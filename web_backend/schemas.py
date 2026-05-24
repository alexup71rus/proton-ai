from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


def _default_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {},
        "required": [],
    }


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


class TrainingStartPayload(BaseModel):
    dataset_name: str
    epochs: int = 1
    batch_size: int = 1
    model_name: str = "tiny-router"
    tokenizer_name: str = "sentencepiece-bpe"


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
    checkpoint_path: str | None = None
    model_path: str | None = None
    tokenizer_path: str | None = None


class TestPayload(BaseModel):
    user_text: str
    answer_allowed: bool = False


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
    execution: ToolExecutionPayload | None = None


class TestDebugPayload(BaseModel):
    candidate_tools: list[str] = Field(default_factory=list)
    serialized_prompt: str = ""
    raw_model_output: str = ""
    repaired_output: str | None = None
    validator_result: dict[str, Any] = Field(default_factory=dict)
    confidence: str = "low"
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


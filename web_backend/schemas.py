from __future__ import annotations

from typing import Any

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


class DatasetsResponse(BaseModel):
    datasets: list[DatasetSummary] = Field(default_factory=list)


class ImportDatasetResponse(BaseModel):
    imported: bool = True
    dataset: DatasetSummary


class GenerateDatasetResponse(BaseModel):
    generated: bool = True
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


class TestResultPayload(BaseModel):
    status: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    response: str | None = None


class TestDebugPayload(BaseModel):
    candidate_tools: list[str] = Field(default_factory=list)
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


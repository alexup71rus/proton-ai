from typing import Any, Literal

from pydantic import BaseModel, Field


class JsonSchema(BaseModel):
    type: Literal["object"]
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str
    description: str
    tags: list[str]
    arguments_schema: JsonSchema


class ToolRegistryRequest(BaseModel):
    tools: list[ToolDefinition]


class ToolRegistryResponse(BaseModel):
    valid: bool
    tool_count: int


class RoutePreviewRequest(BaseModel):
    user_text: str
    tools: list[ToolDefinition]
    answer_allowed: bool = True
    max_candidates: int = 3
    strict_mode: bool = True


class RoutePreviewResponse(BaseModel):
    user_text: str
    candidate_tools: list[str]
    serialized_prompt: str
    model_output: str
    repaired_output: str | None
    validation_error: str | None
    validator_result: dict[str, Any]
    confidence: Literal["high", "low"]
    final_action: Literal["tool_call", "fallback"]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionsRequest(BaseModel):
    messages: list[ChatMessage]
    tools: list[ToolDefinition]
    tool_choice: str = "auto"
    answer_allowed: bool = True


class TrainStartRequest(BaseModel):
    dataset_path: str
    epochs: int = 1
    batch_size: int = 1
    model_name: str = "tiny-router"
    tokenizer_name: str = "sentencepiece-bpe"

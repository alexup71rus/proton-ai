from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(protected_namespaces=())

    user_text: str
    tools: list[ToolDefinition]
    strict_mode: bool = True
    model_path: str | None = None
    tokenizer_path: str | None = None


class RoutePreviewResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    user_text: str
    serialized_prompt: str
    model_output: str
    repaired_output: str | None
    validation_error: str | None
    validator_result: dict[str, Any]
    final_action: Literal["tool_call", "fallback"]
    final_output: dict[str, Any]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    messages: list[ChatMessage]
    tools: list[ToolDefinition]
    tool_choice: str = "auto"
    answer_allowed: bool = True
    model_path: str | None = None
    tokenizer_path: str | None = None


class TrainStartRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    dataset_path: str
    epochs: int = 1
    batch_size: int = 1
    model_name: str = "tiny-router"
    tokenizer_name: str = "sentencepiece-bpe"
    output_root_dir: str = "data"
    artifact_name: str = "tiny_router_v1"
    resume_model_path: str | None = None
    resume_tokenizer_path: str | None = None
    hidden_dim: int = 64
    num_layers: int = 2
    num_heads: int = 4
    learning_rate: float = 1e-3
    training_device: Literal["cpu", "mps", "auto"] | None = None
    vocab_size: int = 512

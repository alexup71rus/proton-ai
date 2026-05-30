from pathlib import Path

from fastapi import FastAPI, HTTPException

from protonx.config import TRAIN_DIR
from protonx.routing.adapter import to_openai_tool_calls
from protonx.routing.inference import preview_route, run_route
from protonx.schemas import ChatCompletionsRequest
from protonx.schemas import RoutePreviewRequest, RoutePreviewResponse
from protonx.schemas import TrainStartRequest
from protonx.schemas import ToolRegistryRequest, ToolRegistryResponse
from protonx.training.dataset_builder import build_synthetic_dataset
from protonx.training.state import TRAINING_STATE
from protonx.training.trainer import get_training_status
from protonx.training.trainer import start_training_job
from protonx.tools import validate_supported_schema_subset, validate_unique_tool_names

app = FastAPI(title="Proton AI Model Service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "proton-ai-model-service", "version": "0.1.0"}


@app.post("/tools/validate", response_model=ToolRegistryResponse)
def validate_tools(payload: ToolRegistryRequest) -> ToolRegistryResponse:
    try:
        validate_unique_tool_names(payload.tools)
        validate_supported_schema_subset(payload.tools)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ToolRegistryResponse(valid=True, tool_count=len(payload.tools))


@app.post("/route/preview", response_model=RoutePreviewResponse)
def route_preview(payload: RoutePreviewRequest) -> RoutePreviewResponse:
    return preview_route(payload)


@app.post("/chat/completions")
def chat_completions(payload: ChatCompletionsRequest) -> dict:
    user_text = payload.messages[-1].content
    decision = run_route(
        RoutePreviewRequest(
            user_text=user_text,
            tools=payload.tools,
            model_path=payload.model_path,
            tokenizer_path=payload.tokenizer_path,
        )
    )
    return to_openai_tool_calls(decision.final_output, answer_allowed=payload.answer_allowed)


@app.post("/train/dataset/build")
def train_dataset_build(payload: ToolRegistryRequest) -> dict:
    output_path = Path(TRAIN_DIR) / "routing.jsonl"
    rows_written = build_synthetic_dataset(payload.tools, output_path)
    return {"rows_written": rows_written, "output_path": str(output_path)}


@app.get("/train/status")
def train_status() -> dict:
    return get_training_status()


@app.post("/train/start")
def train_start(payload: TrainStartRequest) -> dict:
    try:
        return start_training_job(
            dataset_path=Path(payload.dataset_path),
            epochs=payload.epochs,
            batch_size=payload.batch_size,
            model_name=payload.model_name,
            tokenizer_name=payload.tokenizer_name,
            output_root_dir=payload.output_root_dir,
            artifact_name=payload.artifact_name,
            resume_model_path=payload.resume_model_path,
            resume_tokenizer_path=payload.resume_tokenizer_path,
            hidden_dim=payload.hidden_dim,
            num_layers=payload.num_layers,
            num_heads=payload.num_heads,
            learning_rate=payload.learning_rate,
            training_device=payload.training_device,
            vocab_size=payload.vocab_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

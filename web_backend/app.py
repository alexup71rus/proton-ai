from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from web_backend.config import get_tools_file
from web_backend import service_client
from web_backend.datasets import import_dataset_file, list_dataset_files, resolve_dataset_path, summarize_dataset
from web_backend.logs import load_human_logs
from web_backend.schemas import DatasetsResponse, GenerateDatasetResponse, ImportDatasetResponse, LogsResponse, SaveToolsResponse, TestPayload, TestResponse, ToolsPayload, ToolsResponse, TrainingStartPayload, TrainingStatusResponse
from web_backend.tools_store import load_tools, save_tools


app = FastAPI(title="Proton-X UI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8501",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_tools_response(tools: list[dict]) -> ToolsResponse:
    tools_file = get_tools_file()
    return ToolsResponse(
        tools=tools,
        source={
            "name": tools_file.name,
            "path": str(tools_file),
        },
    )


def _normalize_training_status(payload: dict | None) -> TrainingStatusResponse:
    raw = payload or {}
    return TrainingStatusResponse.model_validate(
        {
            "status": raw.get("status") or "idle",
            "current_epoch": raw.get("current_epoch") or 0,
            "total_epochs": raw.get("total_epochs") or 0,
            "current_step": raw.get("current_step") or 0,
            "total_steps": raw.get("total_steps") or 0,
            "loss": raw.get("loss"),
            "loss_history": raw.get("loss_history") or [],
            "metrics": raw.get("metrics") or {},
            "error": raw.get("error"),
            "batch_size": raw.get("batch_size") or 1,
            "model_name": raw.get("model_name") or "tiny-router",
            "tokenizer_name": raw.get("tokenizer_name") or "sentencepiece-bpe",
            "checkpoint_path": raw.get("checkpoint_path"),
            "model_path": raw.get("model_path"),
            "tokenizer_path": raw.get("tokenizer_path"),
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tools", response_model=ToolsResponse)
def get_tools() -> ToolsResponse:
    return _build_tools_response(load_tools())


@app.put("/api/tools", response_model=SaveToolsResponse)
def put_tools(payload: ToolsPayload) -> SaveToolsResponse:
    save_tools([tool.model_dump() for tool in payload.tools])
    response = _build_tools_response([tool.model_dump() for tool in payload.tools])
    return SaveToolsResponse(saved=True, **response.model_dump())


@app.post("/api/tools/validate")
def validate_tools(payload: ToolsPayload) -> dict:
    return service_client.post_json("/tools/validate", payload.model_dump())


@app.get("/api/datasets", response_model=DatasetsResponse)
def get_datasets() -> DatasetsResponse:
    return DatasetsResponse(datasets=[summarize_dataset(path) for path in list_dataset_files()])


@app.post("/api/datasets/import", response_model=ImportDatasetResponse)
async def import_dataset(file: UploadFile = File(...)) -> ImportDatasetResponse:
    target = import_dataset_file(file.filename or "dataset.jsonl", await file.read())
    return ImportDatasetResponse(imported=True, dataset=summarize_dataset(target))


@app.get("/api/datasets/{dataset_name}/download")
def download_dataset(dataset_name: str) -> FileResponse:
    try:
        path = resolve_dataset_path(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return FileResponse(path, filename=path.name, media_type="application/json")


@app.post("/api/datasets/generate", response_model=GenerateDatasetResponse)
def generate_dataset() -> GenerateDatasetResponse:
    tools = load_tools()
    if not tools:
        raise HTTPException(status_code=400, detail="No tools configured. Save at least one tool first.")

    payload = service_client.post_json("/train/dataset/build", {"tools": tools})
    dataset_path = Path(payload["output_path"])
    return GenerateDatasetResponse(
        generated=True,
        rows_written=payload["rows_written"],
        dataset=summarize_dataset(dataset_path),
    )


@app.get("/api/training/status", response_model=TrainingStatusResponse)
def get_training_status() -> TrainingStatusResponse:
    return _normalize_training_status(service_client.get_json("/train/status"))


@app.post("/api/training/start", response_model=TrainingStatusResponse)
def start_training(payload: TrainingStartPayload) -> TrainingStatusResponse:
    try:
        dataset_path = resolve_dataset_path(payload.dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {payload.dataset_name}") from exc

    return _normalize_training_status(
        service_client.post_json(
        "/train/start",
        {
            "dataset_path": str(dataset_path),
            "epochs": payload.epochs,
            "batch_size": payload.batch_size,
            "model_name": payload.model_name,
            "tokenizer_name": payload.tokenizer_name,
        },
        )
    )


@app.post("/api/test", response_model=TestResponse)
def run_test(payload: TestPayload) -> TestResponse:
    tools = load_tools()
    if not tools:
        raise HTTPException(status_code=400, detail="No tools configured. Save at least one tool first.")

    result_payload = service_client.post_json(
        "/chat/completions",
        {
            "messages": [{"role": "user", "content": payload.user_text}],
            "tools": tools,
            "tool_choice": "auto",
            "answer_allowed": payload.answer_allowed,
        },
    )
    debug_payload = service_client.post_json(
        "/route/preview",
        {
            "user_text": payload.user_text,
            "tools": tools,
            "answer_allowed": payload.answer_allowed,
        },
    )

    tool_calls = result_payload.get("tool_calls", [])
    first_call = tool_calls[0] if tool_calls else None
    status = "tool_call" if first_call else "fallback"

    return TestResponse(
        result={
            "status": status,
            "tool_name": first_call.get("name") if first_call else None,
            "arguments": first_call.get("arguments") if first_call else None,
            "response": result_payload.get("response"),
        },
        debug={
            "candidate_tools": debug_payload.get("candidate_tools", []),
            "raw_model_output": debug_payload.get("model_output", ""),
            "repaired_output": debug_payload.get("repaired_output"),
            "validator_result": debug_payload.get("validator_result", {}),
            "confidence": debug_payload.get("confidence", "low"),
            "final_action": debug_payload.get("final_action", "fallback"),
        },
    )


@app.get("/api/logs", response_model=LogsResponse)
def get_logs() -> LogsResponse:
    return LogsResponse(rows=load_human_logs())

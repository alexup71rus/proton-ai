from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from web_backend.config import get_tools_file
from web_backend import service_client
from web_backend.datasets import append_dataset_content, create_manual_dataset, delete_dataset, duplicate_dataset, get_dataset_preview, get_dataset_validation_report, import_dataset_file, list_dataset_files, resolve_dataset_path, save_bootstrap_dataset, summarize_dataset
from web_backend.logs import export_failed_cases_as_dataset, load_human_logs
from web_backend.schemas import DatasetAppendPayload, DatasetBootstrapPayload, DatasetBootstrapResponse, DatasetCreatePayload, DatasetDeleteResponse, DatasetDetailResponse, DatasetDuplicateResponse, DatasetMutationResponse, DatasetValidationReport, DatasetsResponse, ImportDatasetResponse, LogsExportResponse, LogsResponse, SaveToolsResponse, TestPayload, TestResponse, ToolsPayload, ToolsResponse, TrainingStartPayload, TrainingStatusResponse
from web_backend.tools_store import load_tools, save_tools
from web_backend.tool_executor import execute_tool, validate_tool_executor_paths


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


def _to_service_tool(tool: dict) -> dict:
    return {
        "name": tool.get("name", ""),
        "description": tool.get("description", ""),
        "tags": tool.get("tags", []),
        "arguments_schema": tool.get("arguments_schema", {"type": "object", "properties": {}, "required": []}),
    }


def _to_service_tools(tools: list[dict]) -> list[dict]:
    return [_to_service_tool(tool) for tool in tools]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tools", response_model=ToolsResponse)
def get_tools() -> ToolsResponse:
    return _build_tools_response(load_tools())


@app.put("/api/tools", response_model=SaveToolsResponse)
def put_tools(payload: ToolsPayload) -> SaveToolsResponse:
    tools = [tool.model_dump() for tool in payload.tools]
    try:
        validate_tool_executor_paths(tools)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_tools(tools)
    response = _build_tools_response(tools)
    return SaveToolsResponse(saved=True, **response.model_dump())


@app.post("/api/tools/validate")
def validate_tools(payload: ToolsPayload) -> dict:
    tools = [tool.model_dump() for tool in payload.tools]
    try:
        validate_tool_executor_paths(tools)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return service_client.post_json(
        "/tools/validate",
        {"tools": _to_service_tools(tools)},
    )


@app.get("/api/datasets", response_model=DatasetsResponse)
def get_datasets() -> DatasetsResponse:
    return DatasetsResponse(datasets=[summarize_dataset(path) for path in list_dataset_files()])


@app.post("/api/datasets/import", response_model=ImportDatasetResponse)
async def import_dataset(file: UploadFile = File(...)) -> ImportDatasetResponse:
    try:
        target = import_dataset_file(file.filename or "dataset.jsonl", await file.read())
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Dataset file must be UTF-8 encoded") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportDatasetResponse(imported=True, dataset=summarize_dataset(target))


@app.post("/api/datasets/bootstrap", response_model=DatasetBootstrapResponse)
def bootstrap_dataset(payload: DatasetBootstrapPayload) -> DatasetBootstrapResponse:
    tools = load_tools()
    if not tools:
        raise HTTPException(status_code=400, detail="No tools configured. Save at least one tool first.")

    service_payload = service_client.post_json(
        "/train/dataset/build",
        {"tools": _to_service_tools(tools)},
    )
    generated_path = Path(service_payload["output_path"])
    try:
        target = save_bootstrap_dataset(payload.dataset_name, generated_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DatasetBootstrapResponse(
        bootstrapped=True,
        rows_written=service_payload["rows_written"],
        dataset=summarize_dataset(target),
    )


@app.post("/api/datasets/generate", response_model=DatasetBootstrapResponse)
def generate_dataset() -> DatasetBootstrapResponse:
    return bootstrap_dataset(DatasetBootstrapPayload(dataset_name="routing.jsonl"))


@app.post("/api/datasets/manual", response_model=DatasetMutationResponse)
def create_dataset_from_manual_examples(payload: DatasetCreatePayload) -> DatasetMutationResponse:
    try:
        target = create_manual_dataset(payload.dataset_name, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DatasetMutationResponse(saved=True, dataset=summarize_dataset(target))


@app.get("/api/datasets/{dataset_name}/preview", response_model=DatasetDetailResponse)
def preview_dataset(dataset_name: str, limit: int = Query(default=5, ge=1, le=20)) -> DatasetDetailResponse:
    try:
        path = resolve_dataset_path(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return DatasetDetailResponse(**get_dataset_preview(path, limit=limit))


@app.post("/api/datasets/{dataset_name}/validate", response_model=DatasetValidationReport)
def validate_dataset(dataset_name: str) -> DatasetValidationReport:
    try:
        path = resolve_dataset_path(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return DatasetValidationReport(**get_dataset_validation_report(path))


@app.post("/api/datasets/{dataset_name}/append", response_model=DatasetMutationResponse)
def append_dataset(dataset_name: str, payload: DatasetAppendPayload) -> DatasetMutationResponse:
    try:
        path = append_dataset_content(dataset_name, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return DatasetMutationResponse(saved=True, dataset=summarize_dataset(path))


@app.post("/api/datasets/{dataset_name}/duplicate", response_model=DatasetDuplicateResponse)
def duplicate_dataset_file(dataset_name: str) -> DatasetDuplicateResponse:
    try:
        path = duplicate_dataset(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return DatasetDuplicateResponse(duplicated=True, dataset=summarize_dataset(path))


@app.delete("/api/datasets/{dataset_name}", response_model=DatasetDeleteResponse)
def remove_dataset(dataset_name: str) -> DatasetDeleteResponse:
    try:
        deleted_name = delete_dataset(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return DatasetDeleteResponse(deleted=True, name=deleted_name)


@app.get("/api/datasets/{dataset_name}/download")
def download_dataset(dataset_name: str) -> FileResponse:
    try:
        path = resolve_dataset_path(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc
    return FileResponse(path, filename=path.name, media_type="application/json")


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

    validation = get_dataset_validation_report(dataset_path)
    if validation["status"] != "valid":
        first_issue = validation["issues"][0]["message"] if validation["issues"] else "Dataset is invalid"
        raise HTTPException(status_code=400, detail=f"Dataset validation failed: {first_issue}")

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

    service_tools = _to_service_tools(tools)

    result_payload = service_client.post_json(
        "/chat/completions",
        {
            "messages": [{"role": "user", "content": payload.user_text}],
            "tools": service_tools,
            "tool_choice": "auto",
            "answer_allowed": payload.answer_allowed,
        },
    )
    debug_payload = service_client.post_json(
        "/route/preview",
        {
            "user_text": payload.user_text,
            "tools": service_tools,
            "answer_allowed": payload.answer_allowed,
        },
    )

    tool_calls = result_payload.get("tool_calls", [])
    first_call = tool_calls[0] if tool_calls else None
    tool_name = first_call.get("name") if isinstance(first_call, dict) else None
    arguments = first_call.get("arguments") if isinstance(first_call, dict) else None
    selected_tool = next((tool for tool in tools if tool.get("name") == tool_name), None)
    execution = execute_tool(selected_tool, arguments) if selected_tool else None
    status = "tool_call" if tool_name else "fallback"

    return TestResponse(
        result={
            "status": status,
            "tool_name": tool_name,
            "arguments": arguments,
            "response": result_payload.get("response"),
            "execution": execution,
        },
        debug={
            "candidate_tools": debug_payload.get("candidate_tools", []),
            "serialized_prompt": debug_payload.get("serialized_prompt", ""),
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


@app.post("/api/logs/export-failed-cases", response_model=LogsExportResponse)
def export_failed_cases() -> LogsExportResponse:
    rows = export_failed_cases_as_dataset(load_tools())
    if not rows:
        raise HTTPException(status_code=400, detail="No failed log rows available for export.")

    dataset_name = datetime.utcnow().strftime("logs-draft-%Y%m%d-%H%M%S.jsonl")
    try:
        from web_backend.datasets import write_dataset_file

        target = write_dataset_file(
            dataset_name,
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
            source="logs_draft",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LogsExportResponse(exported=True, rows_written=len(rows), dataset=summarize_dataset(target))

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from service.protonx.training.common import normalize_artifact_name as normalize_training_artifact_name

from web_backend.config import get_tools_file
from web_backend import service_client
from web_backend.datasets import append_dataset_content, create_manual_dataset, delete_dataset, duplicate_dataset, get_dataset_preview, get_dataset_validation_report, import_dataset_file, list_dataset_files, resolve_dataset_path, save_bootstrap_dataset, summarize_dataset
from web_backend.dataset_validation import FALLBACK_TOOL_NAME
from web_backend.logs import export_failed_cases_as_dataset, load_human_logs
from web_backend.schemas import DatasetAppendPayload, DatasetBootstrapPayload, DatasetBootstrapResponse, DatasetCreatePayload, DatasetDeleteResponse, DatasetDetailResponse, DatasetDuplicateResponse, DatasetMutationResponse, DatasetValidationReport, DatasetsResponse, ImportDatasetResponse, LogsExportResponse, LogsResponse, ModelImportResponse, SaveToolsResponse, TestPayload, TestResponse, ToolsPayload, ToolsResponse, TrainingStartPayload, TrainingStatusResponse, WorkspaceModelSettings, WorkspaceSettingsPayload, WorkspaceSettingsResponse, WorkspaceTestSettings, WorkspaceTrainingSettings
from web_backend.tools_store import load_tools, save_tools
from web_backend.tool_executor import execute_tool, validate_tool_executor_paths
from web_backend.workspace_store import load_workspace_settings, save_workspace_settings, update_workspace_settings


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
    return TrainingStatusResponse.from_service_payload(payload)


def _to_service_tool(tool: dict) -> dict:
    return {
        "name": tool.get("name", ""),
        "description": tool.get("description", ""),
        "tags": tool.get("tags", []),
        "arguments_schema": tool.get("arguments_schema", {"type": "object", "properties": {}, "required": []}),
    }


def _to_service_tools(tools: list[dict]) -> list[dict]:
    return [_to_service_tool(tool) for tool in tools]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_output_root(output_root_dir: str) -> Path:
    path = Path(output_root_dir).expanduser()
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _normalize_artifact_name(artifact_name: str) -> str:
    try:
        return normalize_training_artifact_name(artifact_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _load_workspace_settings() -> WorkspaceSettingsResponse:
    try:
        return load_workspace_settings()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _save_workspace_settings(payload: WorkspaceSettingsPayload | dict) -> WorkspaceSettingsResponse:
    try:
        return save_workspace_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _update_workspace_settings(updates: dict) -> WorkspaceSettingsResponse:
    try:
        return update_workspace_settings(updates)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _workspace_sections(
    workspace: WorkspaceSettingsResponse,
) -> tuple[WorkspaceModelSettings, WorkspaceTrainingSettings, WorkspaceTestSettings]:
    return (
        cast(WorkspaceModelSettings, workspace.selected_model),
        cast(WorkspaceTrainingSettings, workspace.training),
        cast(WorkspaceTestSettings, workspace.test),
    )


def _coalesce_str(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback
    normalized = value.strip()
    return normalized or fallback


def _coalesce_int(value: int | None, fallback: int) -> int:
    return fallback if value is None else value


def _extract_tool_response(execution: dict | None) -> str | None:
    if not execution or execution.get("error"):
        return None
    output = execution.get("output")
    if not isinstance(output, dict):
        return None
    response = output.get("response")
    if not isinstance(response, str):
        return None
    response = response.strip()
    return response or None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/workspace", response_model=WorkspaceSettingsResponse)
def get_workspace_settings() -> WorkspaceSettingsResponse:
    return _load_workspace_settings()


@app.put("/api/workspace", response_model=WorkspaceSettingsResponse)
def put_workspace_settings(payload: WorkspaceSettingsPayload) -> WorkspaceSettingsResponse:
    return _save_workspace_settings(payload)


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
    status = _normalize_training_status(service_client.get_json("/train/status"))
    updates: dict[str, dict[str, object]] = {}

    if status.dataset_path:
        updates["training"] = {"dataset_name": Path(status.dataset_path).name}

    if status.model_path and status.tokenizer_path:
        workspace = _load_workspace_settings()
        selected_model, _training, _test = _workspace_sections(workspace)
        updates["selected_model"] = {
            "mode": "loaded",
            "label": status.artifact_name or selected_model.label,
            "model_name": status.model_name or selected_model.model_name,
            "tokenizer_name": status.tokenizer_name or selected_model.tokenizer_name,
            "output_root_dir": status.output_root_dir or selected_model.output_root_dir,
            "artifact_name": status.artifact_name or selected_model.artifact_name,
            "model_path": status.model_path,
            "tokenizer_path": status.tokenizer_path,
        }

    if updates:
        _update_workspace_settings(updates)

    return status


@app.post("/api/models/import", response_model=ModelImportResponse)
async def import_model(
    checkpoint: UploadFile = File(...),
    tokenizer: UploadFile = File(...),
    vocab: UploadFile | None = File(default=None),
    output_root_dir: str = Form(default="data"),
    artifact_name: str = Form(default="tiny_router_v1"),
) -> ModelImportResponse:
    normalized_artifact_name = _normalize_artifact_name(artifact_name)
    resolved_output_root = _resolve_output_root(output_root_dir)
    weights_dir = resolved_output_root / "weights"
    tokenizers_dir = resolved_output_root / "tokenizers"
    weights_dir.mkdir(parents=True, exist_ok=True)
    tokenizers_dir.mkdir(parents=True, exist_ok=True)

    model_path = weights_dir / f"{normalized_artifact_name}.pt"
    tokenizer_path = tokenizers_dir / f"{normalized_artifact_name}.model"
    model_path.write_bytes(await checkpoint.read())
    tokenizer_path.write_bytes(await tokenizer.read())

    if vocab is not None:
        vocab_path = tokenizers_dir / f"{normalized_artifact_name}.vocab"
        vocab_path.write_bytes(await vocab.read())

    workspace = _load_workspace_settings()
    selected_model, _training, _test = _workspace_sections(workspace)
    _update_workspace_settings(
        {
            "selected_model": {
                "mode": "loaded",
                "label": normalized_artifact_name,
                "model_name": selected_model.model_name,
                "tokenizer_name": selected_model.tokenizer_name,
                "output_root_dir": str(resolved_output_root),
                "artifact_name": normalized_artifact_name,
                "model_path": str(model_path),
                "tokenizer_path": str(tokenizer_path),
            }
        }
    )

    return ModelImportResponse(
        imported=True,
        output_root_dir=str(resolved_output_root),
        artifact_name=normalized_artifact_name,
        model_path=str(model_path),
        tokenizer_path=str(tokenizer_path),
    )


@app.post("/api/training/start", response_model=TrainingStatusResponse)
def start_training(payload: TrainingStartPayload) -> TrainingStatusResponse:
    workspace = _load_workspace_settings()
    selected_model, training_settings, _test_settings = _workspace_sections(workspace)
    payload_fields = payload.model_fields_set

    dataset_name = _coalesce_str(payload.dataset_name, training_settings.dataset_name)
    epochs = _coalesce_int(payload.epochs, training_settings.epochs)
    batch_size = _coalesce_int(payload.batch_size, training_settings.batch_size)
    model_name = _coalesce_str(payload.model_name, selected_model.model_name)
    tokenizer_name = _coalesce_str(payload.tokenizer_name, selected_model.tokenizer_name)
    output_root_dir = _coalesce_str(payload.output_root_dir, selected_model.output_root_dir)
    artifact_name = _normalize_artifact_name(_coalesce_str(payload.artifact_name, selected_model.artifact_name))
    hidden_dim = _coalesce_int(payload.hidden_dim, selected_model.hidden_dim)
    num_layers = _coalesce_int(payload.num_layers, selected_model.num_layers)
    num_heads = _coalesce_int(payload.num_heads, selected_model.num_heads)

    if "resume_model_path" in payload_fields:
        resume_model_path = payload.resume_model_path
    elif selected_model.mode == "loaded":
        resume_model_path = selected_model.model_path
    else:
        resume_model_path = None

    if "resume_tokenizer_path" in payload_fields:
        resume_tokenizer_path = payload.resume_tokenizer_path
    elif selected_model.mode == "loaded":
        resume_tokenizer_path = selected_model.tokenizer_path
    else:
        resume_tokenizer_path = None

    try:
        dataset_path = resolve_dataset_path(dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}") from exc

    validation = get_dataset_validation_report(dataset_path)
    if validation["status"] != "valid":
        first_issue = validation["issues"][0]["message"] if validation["issues"] else "Dataset is invalid"
        raise HTTPException(status_code=400, detail=f"Dataset validation failed: {first_issue}")

    _update_workspace_settings(
        {
            "training": {
                "dataset_name": dataset_name,
                "epochs": epochs,
                "batch_size": batch_size,
            },
            "selected_model": {
                "mode": "loaded" if resume_model_path and resume_tokenizer_path else "new",
                "label": artifact_name,
                "model_name": model_name,
                "tokenizer_name": tokenizer_name,
                "output_root_dir": output_root_dir,
                "artifact_name": artifact_name,
                "model_path": resume_model_path,
                "tokenizer_path": resume_tokenizer_path,
                "hidden_dim": hidden_dim,
                "num_layers": num_layers,
                "num_heads": num_heads,
            },
        }
    )

    return _normalize_training_status(
        service_client.post_json(
        "/train/start",
        {
            "dataset_path": str(dataset_path),
            "epochs": epochs,
            "batch_size": batch_size,
            "model_name": model_name,
            "tokenizer_name": tokenizer_name,
            "output_root_dir": output_root_dir,
            "artifact_name": artifact_name,
            "resume_model_path": resume_model_path,
            "resume_tokenizer_path": resume_tokenizer_path,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "num_heads": num_heads,
        },
        )
    )


@app.post("/api/test", response_model=TestResponse)
def run_test(payload: TestPayload) -> TestResponse:
    tools = load_tools()
    if not tools:
        raise HTTPException(status_code=400, detail="No tools configured. Save at least one tool first.")

    service_tools = _to_service_tools(tools)
    workspace = _load_workspace_settings()
    selected_model, _training_settings, _test_settings = _workspace_sections(workspace)
    model_path = payload.model_path or selected_model.model_path
    tokenizer_path = payload.tokenizer_path or selected_model.tokenizer_path
    debug_payload = service_client.post_json(
        "/route/preview",
        {
            "user_text": payload.user_text,
            "tools": service_tools,
            "model_path": model_path,
            "tokenizer_path": tokenizer_path,
        },
    )

    final_output = debug_payload.get("final_output", {})
    tool_calls = final_output.get("tool_calls", []) if isinstance(final_output, dict) else []
    first_call = next(
        (
            call
            for call in tool_calls
            if isinstance(call, dict) and call.get("name") != FALLBACK_TOOL_NAME
        ),
        None,
    )
    tool_name = first_call.get("name") if isinstance(first_call, dict) else None
    arguments = first_call.get("arguments") if isinstance(first_call, dict) else None
    selected_tool = next((tool for tool in tools if tool.get("name") == tool_name), None)
    execution = execute_tool(selected_tool, arguments) if selected_tool else None
    status = "tool_call" if tool_name else "fallback"
    response_text = _extract_tool_response(execution)

    return TestResponse(
        result={
            "status": status,
            "tool_name": tool_name,
            "arguments": arguments,
            "response": response_text,
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

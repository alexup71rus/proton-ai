from dataclasses import dataclass
from pathlib import Path

from protonx.config import ROOT_DIR, TOKENIZER_DIR, WEIGHTS_DIR
from protonx.contracts import build_fallback_payload
from protonx.contracts import with_fallback_tool
from protonx.logging import append_router_log
from protonx.routing.model_runtime import ModelRuntime
from protonx.routing.prompt import build_routing_prompt
from protonx.routing.validate import validate_model_output
from protonx.schemas import RoutePreviewRequest, RoutePreviewResponse
from protonx.training.format import serialize_inference_prompt


MODEL_RUNTIME = ModelRuntime(
    Path(WEIGHTS_DIR) / "router.pt",
    Path(TOKENIZER_DIR) / "router.model",
)


@dataclass
class RoutingDecision:
    serialized_prompt: str
    model_output: str
    repaired_output: str | None
    validation_error: str | None
    validator_result: dict
    final_action: str
    final_output: dict


def _sync_model_runtime_paths(
    model_path: str | None = None,
    tokenizer_path: str | None = None,
) -> None:
    def resolve_artifact_path(raw_path: str | None, fallback: Path) -> Path:
        if not raw_path:
            return fallback
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        return ROOT_DIR / path

    next_weights_path = resolve_artifact_path(
        model_path,
        Path(WEIGHTS_DIR) / "router.pt",
    )
    next_tokenizer_path = (
        resolve_artifact_path(tokenizer_path, Path(TOKENIZER_DIR) / "router.model")
    )
    if (
        MODEL_RUNTIME.weights_path != next_weights_path
        or MODEL_RUNTIME.tokenizer_path != next_tokenizer_path
    ):
        MODEL_RUNTIME.weights_path = next_weights_path
        MODEL_RUNTIME.tokenizer_path = next_tokenizer_path
        MODEL_RUNTIME._clear_cached_runtime()


def _append_fallback_log(
    *,
    user_text: str,
    available_tools: list[str],
    model_output: str,
    repaired_output: str | None,
    validation_error: str | None,
    validator_result: dict,
) -> None:
    append_router_log(
        {
            "user_text": user_text,
            "available_tools": available_tools,
            "model_output": model_output,
            "repaired_output": repaired_output,
            "validation_error": validation_error,
            "validator_result": validator_result,
            "final_action": "fallback",
        }
    )


def run_route(payload: RoutePreviewRequest) -> RoutingDecision:
    available_tools = with_fallback_tool(payload.tools)
    prompt = build_routing_prompt(payload.user_text, available_tools)
    serialized_prompt = serialize_inference_prompt(prompt)
    _sync_model_runtime_paths(payload.model_path, payload.tokenizer_path)
    model_output = MODEL_RUNTIME.generate(prompt)
    repaired_output = None
    validation = validate_model_output(
        available_tools,
        model_output,
        strict_mode=payload.strict_mode,
    )

    if validation.final_action == "fallback":
        final_output = build_fallback_payload()
    elif validation.valid and validation.parsed_output is not None:
        final_output = validation.parsed_output
    else:
        final_output = build_fallback_payload()

    validator_result = {
        "valid": validation.valid,
        "error": validation.error,
        "final_action": validation.final_action,
    }
    if validation.final_action == "fallback":
        _append_fallback_log(
            user_text=payload.user_text,
            available_tools=[tool.name for tool in available_tools],
            model_output=model_output,
            repaired_output=repaired_output,
            validation_error=validation.error,
            validator_result=validator_result,
        )

    return RoutingDecision(
        serialized_prompt=serialized_prompt,
        model_output=model_output,
        repaired_output=repaired_output,
        validation_error=validation.error,
        validator_result=validator_result,
        final_action=validation.final_action,
        final_output=final_output,
    )


def preview_route(payload: RoutePreviewRequest) -> RoutePreviewResponse:
    decision = run_route(payload)
    return RoutePreviewResponse(
        user_text=payload.user_text,
        serialized_prompt=decision.serialized_prompt,
        model_output=decision.model_output,
        repaired_output=decision.repaired_output,
        validation_error=decision.validation_error,
        validator_result=decision.validator_result,
        final_action=decision.final_action,
        final_output=decision.final_output,
    )

from dataclasses import dataclass
from pathlib import Path

from protonx.config import TOKENIZER_DIR, WEIGHTS_DIR
from protonx.contracts import build_fallback_tool
from protonx.contracts import build_fallback_payload
from protonx.logging import append_router_log
from protonx.routing.filter import score_candidate_tools, select_candidate_tools
from protonx.routing.model_runtime import ModelRuntime
from protonx.routing.prompt import build_routing_prompt
from protonx.routing.repair import repair_json_syntax
from protonx.routing.validate import validate_model_output
from protonx.schemas import RoutePreviewRequest, RoutePreviewResponse
from protonx.training.format import serialize_inference_prompt


MODEL_RUNTIME = ModelRuntime(
    Path(WEIGHTS_DIR) / "tiny_router_v1.pt",
    Path(TOKENIZER_DIR) / "routing_spm.model",
)


@dataclass
class RoutingDecision:
    candidate_tools: list[str]
    serialized_prompt: str
    model_output: str
    repaired_output: str | None
    validation_error: str | None
    validator_result: dict
    confidence: str
    final_action: str
    final_output: dict


def _positive_candidate_names(
    scored_candidates: list[tuple], max_candidates: int
) -> list[str]:
    return [
        tool.name
        for tool, score in scored_candidates[:max_candidates]
        if score > 0
    ]


def _sync_model_runtime_paths(
    model_path: str | None = None,
    tokenizer_path: str | None = None,
) -> None:
    next_weights_path = (
        Path(model_path)
        if model_path
        else Path(WEIGHTS_DIR) / "tiny_router_v1.pt"
    )
    next_tokenizer_path = (
        Path(tokenizer_path)
        if tokenizer_path
        else Path(TOKENIZER_DIR) / "routing_spm.model"
    )
    if (
        MODEL_RUNTIME.weights_path != next_weights_path
        or MODEL_RUNTIME.tokenizer_path != next_tokenizer_path
    ):
        MODEL_RUNTIME.weights_path = next_weights_path
        MODEL_RUNTIME.tokenizer_path = next_tokenizer_path
        MODEL_RUNTIME._clear_cached_runtime()


def run_route(payload: RoutePreviewRequest) -> RoutingDecision:
    scored_candidates = score_candidate_tools(payload.user_text, payload.tools)
    selected_candidates = select_candidate_tools(
        payload.user_text, payload.tools, payload.max_candidates
    )
    candidate_names = _positive_candidate_names(scored_candidates, payload.max_candidates)
    if not selected_candidates:
        candidates = [build_fallback_tool()]
    else:
        candidates = selected_candidates

    if len(scored_candidates) > 1:
        top_score = scored_candidates[0][1]
        second_score = scored_candidates[1][1]
        if top_score > 0 and (top_score - second_score) <= 0:
            return RoutingDecision(
                candidate_tools=[tool.name for tool in selected_candidates],
                serialized_prompt="",
                model_output="",
                repaired_output=None,
                validation_error="low confidence candidate match",
                validator_result={
                    "valid": False,
                    "error": "low confidence candidate match",
                    "final_action": "fallback",
                },
                confidence="low",
                final_action="fallback",
                final_output=build_fallback_payload(),
            )

    prompt = build_routing_prompt(
        payload.user_text, candidates, payload.answer_allowed
    )
    serialized_prompt = serialize_inference_prompt(prompt)
    _sync_model_runtime_paths(payload.model_path, payload.tokenizer_path)
    model_output = MODEL_RUNTIME.generate(prompt)
    repaired_output = repair_json_syntax(model_output)
    validation = validate_model_output(
        candidates,
        repaired_output or "",
        payload.answer_allowed,
        strict_mode=payload.strict_mode,
    )

    if not validation.valid:
        append_router_log(
            {
                "user_text": payload.user_text,
                "candidate_tools": [tool.name for tool in selected_candidates],
                "model_output": model_output,
                "validation_error": validation.error,
                "final_action": "fallback",
            }
        )

    if validation.final_action == "fallback" and repaired_output is None:
        repaired_output = model_output

    if validation.final_action == "fallback":
        final_output = build_fallback_payload()
    elif validation.valid and validation.parsed_output is not None:
        final_output = validation.parsed_output
    else:
        final_output = build_fallback_payload()
    return RoutingDecision(
        candidate_tools=candidate_names,
        serialized_prompt=serialized_prompt,
        model_output=model_output,
        repaired_output=repaired_output,
        validation_error=validation.error,
        validator_result={
            "valid": validation.valid,
            "error": validation.error,
            "final_action": validation.final_action,
        },
        confidence="high" if validation.valid else "low",
        final_action=validation.final_action,
        final_output=final_output,
    )


def preview_route(payload: RoutePreviewRequest) -> RoutePreviewResponse:
    decision = run_route(payload)
    return RoutePreviewResponse(
        user_text=payload.user_text,
        candidate_tools=decision.candidate_tools,
        serialized_prompt=decision.serialized_prompt,
        model_output=decision.model_output,
        repaired_output=decision.repaired_output,
        validation_error=decision.validation_error,
        validator_result=decision.validator_result,
        confidence=decision.confidence,
        final_action=decision.final_action,
    )

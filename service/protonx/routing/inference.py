from dataclasses import dataclass
from pathlib import Path

from protonx.config import TOKENIZER_DIR, WEIGHTS_DIR
from protonx.contracts import build_fallback_payload
from protonx.logging import append_router_log
from protonx.routing.filter import score_candidate_tools, select_candidate_tools
from protonx.routing.model_runtime import ModelRuntime
from protonx.routing.prompt import build_routing_prompt
from protonx.routing.repair import repair_json_syntax
from protonx.routing.validate import validate_model_output
from protonx.schemas import RoutePreviewRequest, RoutePreviewResponse


MODEL_RUNTIME = ModelRuntime(
    Path(WEIGHTS_DIR) / "tiny_router_v1.pt",
    Path(TOKENIZER_DIR) / "routing_spm.model",
)


@dataclass
class RoutingDecision:
    candidate_tools: list[str]
    model_output: str
    repaired_output: str | None
    validation_error: str | None
    validator_result: dict
    confidence: str
    final_action: str
    final_output: dict


def run_route(payload: RoutePreviewRequest) -> RoutingDecision:
    scored_candidates = score_candidate_tools(payload.user_text, payload.tools)
    candidates = select_candidate_tools(
        payload.user_text, payload.tools, payload.max_candidates
    )
    if not candidates:
        return RoutingDecision(
            candidate_tools=[],
            model_output="",
            repaired_output=None,
            validation_error=None,
            validator_result={"valid": False, "error": "no candidate tools", "final_action": "fallback"},
            confidence="low",
            final_action="fallback",
            final_output=build_fallback_payload(payload.answer_allowed),
        )
    if len(scored_candidates) > 1:
        top_score = scored_candidates[0][1]
        second_score = scored_candidates[1][1]
        if top_score > 0 and (top_score - second_score) <= 0:
            return RoutingDecision(
                candidate_tools=[tool.name for tool in candidates],
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
                final_output=build_fallback_payload(payload.answer_allowed),
            )

    prompt = build_routing_prompt(
        payload.user_text, candidates, payload.answer_allowed
    )
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
                "candidate_tools": [tool.name for tool in candidates],
                "model_output": model_output,
                "validation_error": validation.error,
                "final_action": "fallback",
            }
        )

    if validation.final_action == "fallback" and repaired_output is None:
        repaired_output = model_output

    final_output = (
        validation.parsed_output
        if validation.valid and validation.parsed_output is not None
        else build_fallback_payload(payload.answer_allowed)
    )
    return RoutingDecision(
        candidate_tools=[tool.name for tool in candidates],
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
        model_output=decision.model_output,
        repaired_output=decision.repaired_output,
        validation_error=decision.validation_error,
        validator_result=decision.validator_result,
        confidence=decision.confidence,
        final_action=decision.final_action,
    )

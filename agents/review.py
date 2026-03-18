from prompts import build_review_prompt
from pydantic import ValidationError
from state import AgentState, ReviewResult
from tools.comparison_contract import build_scorecards_from_criteria
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.reporting import build_report_spec
from tools.validation import validate_final_delivery_state


def review_agent(state: AgentState) -> AgentState:
    """Review comparison outputs and request a targeted revision if needed."""
    config = state["config"]
    try:
        report_spec = build_report_spec(state)
    except Exception as exc:
        validation = validate_final_delivery_state(state)
        if validation.hard_errors:
            return {
                "validation_warnings": validation.soft_warnings,
                "status": "failed",
                "last_error": validation.hard_errors[0],
            }
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    compatibility_inputs = _build_review_compatibility_inputs(state, report_spec)
    prompt = build_review_prompt(
        market_context_summary=state.get("market_context_summary", ""),
        comparison_matrix=compatibility_inputs["comparison_matrix"],
        swot_matrix=compatibility_inputs["swot_matrix"],
        scorecard=compatibility_inputs["scorecard"],
        low_confidence_claims=state.get("low_confidence_claims", []),
        report_spec=report_spec,
        validation_warnings=state.get("validation_warnings", []),
    )

    try:
        result = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=ReviewResult,
        )
        result = ReviewResult.model_validate(result)
    except (StructuredOutputError, ValidationError) as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    normalized_result = (
        ReviewResult(passed=True, revision_target=None, review_issues=[])
        if result.passed
        else ReviewResult(
            passed=False,
            revision_target=result.revision_target or "supervisor_synthesis",
            review_issues=result.review_issues or ["근거 또는 비교 논리가 충분하지 않음"],
        )
    )
    validated_state = {
        **state,
        "report_spec": report_spec,
        "review_result": normalized_result,
    }
    final_validation = validate_final_delivery_state(validated_state)
    if final_validation.hard_errors:
        return {
            "report_spec": report_spec,
            "review_result": normalized_result,
            "review_issues": normalized_result.review_issues,
            "validation_warnings": final_validation.soft_warnings,
            "status": "failed",
            "last_error": final_validation.hard_errors[0],
        }

    if normalized_result.passed:
        return {
            "report_spec": report_spec,
            "review_result": normalized_result,
            "review_issues": [],
            "validation_warnings": final_validation.soft_warnings,
            "schema_retry_count": 0,
            "status": "reviewed",
            "last_error": None,
        }

    review_issues = normalized_result.review_issues
    return {
        "report_spec": report_spec,
        "review_result": normalized_result,
        "review_issues": review_issues,
        "validation_warnings": final_validation.soft_warnings,
        "schema_retry_count": 0,
        "status": "reviewed",
        "last_error": None,
    }


def _build_review_compatibility_inputs(state: AgentState, report_spec) -> dict[str, list]:
    return {
        "comparison_matrix": report_spec.quick_comparison_panel or state.get("comparison_matrix", []),
        "swot_matrix": report_spec.swot_matrix or state.get("swot_matrix", []),
        "scorecard": build_scorecards_from_criteria(report_spec.score_criteria)
        or state.get("scorecard", []),
    }

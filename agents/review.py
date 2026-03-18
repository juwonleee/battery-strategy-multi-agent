from prompts import build_review_prompt
from state import AgentState, ReviewResult
from tools.openai_client import StructuredOutputError, invoke_structured_output


def review_agent(state: AgentState) -> AgentState:
    """Review comparison outputs and request a targeted revision if needed."""
    config = state["config"]
    prompt = build_review_prompt(
        market_context_summary=state.get("market_context_summary", ""),
        comparison_matrix=state.get("comparison_matrix", []),
        swot_matrix=state.get("swot_matrix", []),
        scorecard=state.get("scorecard", []),
        low_confidence_claims=state.get("low_confidence_claims", []),
    )

    try:
        result = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=ReviewResult,
        )
    except StructuredOutputError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    if result.passed:
        result = ReviewResult(passed=True, revision_target=None, review_issues=[])
        return {
            "review_result": result,
            "review_issues": [],
            "schema_retry_count": 0,
            "status": "reviewed",
            "last_error": None,
        }

    revision_target = result.revision_target or "comparison"
    review_issues = result.review_issues or ["근거 또는 비교 논리가 충분하지 않음"]
    return {
        "review_result": ReviewResult(
            passed=False,
            revision_target=revision_target,
            review_issues=review_issues,
        ),
        "review_issues": review_issues,
        "schema_retry_count": 0,
        "status": "reviewed",
        "last_error": None,
    }

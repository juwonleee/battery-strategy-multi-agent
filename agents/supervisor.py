from state import AgentState, WorkflowStep


REVIEW_INVALIDATIONS: dict[WorkflowStep, tuple[str, ...]] = {
    "market_research": (
        "market_context",
        "market_context_summary",
        "lges_profile",
        "catl_profile",
        "comparison_matrix",
        "swot_matrix",
        "scorecard",
        "low_confidence_claims",
        "review_result",
        "review_issues",
    ),
    "lges_analysis": (
        "lges_profile",
        "comparison_matrix",
        "swot_matrix",
        "scorecard",
        "low_confidence_claims",
        "review_result",
        "review_issues",
    ),
    "catl_analysis": (
        "catl_profile",
        "comparison_matrix",
        "swot_matrix",
        "scorecard",
        "low_confidence_claims",
        "review_result",
        "review_issues",
    ),
    "comparison": (
        "comparison_matrix",
        "swot_matrix",
        "scorecard",
        "low_confidence_claims",
        "review_result",
        "review_issues",
    ),
    "review": (
        "review_result",
        "review_issues",
    ),
}


def supervisor_agent(state: AgentState) -> AgentState:
    """Route workflow execution, including schema retries and review revisions."""
    retry_budget = state["retry_budget"]
    current_step = state.get("current_step")

    if state.get("status") == "failed":
        attempt = state.get("schema_retry_count", 0)
        if current_step in REVIEW_INVALIDATIONS and attempt < retry_budget.schema_validation_max:
            return {
                "current_step": current_step,
                "schema_retry_count": attempt + 1,
                "status": "routing",
            }
        return {"current_step": "finish", "status": "failed"}

    review_result = state.get("review_result")
    if review_result and not review_result.passed:
        attempt = state.get("review_retry_count", 0)
        if attempt >= retry_budget.review_max:
            return {"current_step": "finish", "status": "failed"}
        revision_target = review_result.revision_target or "comparison"
        return {
            "current_step": revision_target,
            "review_retry_count": attempt + 1,
            "schema_retry_count": 0,
            "status": "routing",
            **_build_revision_reset(revision_target),
        }

    if not state.get("market_context"):
        return {"current_step": "market_research", "status": "routing"}
    if not state.get("lges_profile"):
        return {"current_step": "lges_analysis", "status": "routing"}
    if not state.get("catl_profile"):
        return {"current_step": "catl_analysis", "status": "routing"}
    if not state.get("comparison_matrix"):
        return {"current_step": "comparison", "status": "routing"}
    if not review_result:
        return {"current_step": "review", "status": "routing"}
    return {"current_step": "finish", "status": "completed"}


def _build_revision_reset(step: WorkflowStep) -> dict[str, object]:
    cleared: dict[str, object] = {}
    for key in REVIEW_INVALIDATIONS.get(step, ()):
        if key in {"comparison_matrix", "swot_matrix", "scorecard", "low_confidence_claims", "review_issues"}:
            cleared[key] = []
        else:
            cleared[key] = None
    return cleared

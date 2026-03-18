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
    """Route workflow execution, including retries, revisions, and terminal exits."""
    retry_budget = state["retry_budget"]
    current_step = state.get("current_step")

    if state.get("status") == "failed":
        attempt = state.get("schema_retry_count", 0)
        if current_step in REVIEW_INVALIDATIONS and attempt < retry_budget.schema_validation_max:
            return {
                "current_step": current_step,
                "routing_reason": (
                    f"Retrying {current_step} after failure "
                    f"({attempt + 1}/{retry_budget.schema_validation_max})."
                ),
                "schema_retry_count": attempt + 1,
                "status": "routing",
            }
        return {
            "current_step": "finish",
            "routing_reason": (
                f"Stopping after {current_step} failed and exhausted schema retries."
            ),
            "status": "failed",
        }

    review_result = state.get("review_result")
    if review_result and not review_result.passed:
        attempt = state.get("review_retry_count", 0)
        revision_target = review_result.revision_target or "comparison"
        if attempt >= retry_budget.review_max:
            return {
                "current_step": "finish",
                "routing_reason": (
                    f"Stopping after review requested {revision_target} revision "
                    "and review retry budget was exhausted."
                ),
                "status": "failed",
            }
        return {
            "current_step": revision_target,
            "routing_reason": (
                f"Review requested revision for {revision_target} "
                f"({attempt + 1}/{retry_budget.review_max})."
            ),
            "review_retry_count": attempt + 1,
            "schema_retry_count": 0,
            "status": "routing",
            **_build_revision_reset(revision_target),
        }

    if not state.get("market_context"):
        return {
            "current_step": "market_research",
            "routing_reason": "Market context is missing, so market research must run first.",
            "status": "routing",
        }
    if not state.get("lges_profile"):
        return {
            "current_step": "lges_analysis",
            "routing_reason": "LGES profile is missing, so LGES analysis runs next.",
            "status": "routing",
        }
    if not state.get("catl_profile"):
        return {
            "current_step": "catl_analysis",
            "routing_reason": "CATL profile is missing, so CATL analysis runs next.",
            "status": "routing",
        }
    if not state.get("comparison_matrix"):
        return {
            "current_step": "comparison",
            "routing_reason": "Comparison outputs are missing, so comparison generation runs next.",
            "status": "routing",
        }
    if not review_result:
        return {
            "current_step": "review",
            "routing_reason": "Comparison outputs are ready, so review runs next.",
            "status": "routing",
        }
    return {
        "current_step": "finish",
        "routing_reason": "Review passed and the workflow reached a terminal completed state.",
        "status": "completed",
    }


def _build_revision_reset(step: WorkflowStep) -> dict[str, object]:
    cleared: dict[str, object] = {}
    for key in REVIEW_INVALIDATIONS.get(step, ()):
        if key in {
            "comparison_matrix",
            "swot_matrix",
            "scorecard",
            "low_confidence_claims",
            "review_issues",
        }:
            cleared[key] = []
        else:
            cleared[key] = None
    return cleared

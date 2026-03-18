from copy import deepcopy

from agents.supervisor import supervisor_agent
from state import ReviewResult


def test_supervisor_routes_market_research_when_market_context_missing(sample_state):
    state = deepcopy(sample_state)
    state["market_context"] = None
    state["market_context_summary"] = ""

    routed = supervisor_agent(state)

    assert routed["current_step"] == "market_research"
    assert "market research" in routed["routing_reason"].lower()


def test_supervisor_retries_failed_schema_step_within_budget(sample_state):
    state = deepcopy(sample_state)
    state["current_step"] = "comparison"
    state["status"] = "failed"
    state["schema_retry_count"] = 0
    state["last_error"] = "comparison row missing evidence"
    state["retry_budget"].schema_validation_max = 5

    routed = supervisor_agent(state)

    assert routed["current_step"] == "comparison"
    assert routed["schema_retry_count"] == 1
    assert routed["status"] == "routing"


def test_supervisor_routes_review_revision_and_clears_downstream_outputs(sample_state):
    state = deepcopy(sample_state)
    state["review_result"] = ReviewResult(
        passed=False,
        revision_target="comparison",
        review_issues=["score rationale is weak"],
    )
    state["review_retry_count"] = 0
    state["retry_budget"].review_max = 5

    routed = supervisor_agent(state)

    assert routed["current_step"] == "comparison"
    assert routed["review_retry_count"] == 1
    assert routed["comparison_matrix"] == []
    assert routed["charts"] == []
    assert routed["scorecard"] == []
    assert "revision" in routed["routing_reason"].lower()


def test_supervisor_finishes_when_review_has_passed(sample_state):
    routed = supervisor_agent(sample_state)

    assert routed["current_step"] == "finish"
    assert routed["status"] == "completed"


def test_supervisor_stops_after_single_schema_retry_even_if_budget_is_higher(sample_state):
    state = deepcopy(sample_state)
    state["current_step"] = "comparison"
    state["status"] = "failed"
    state["schema_retry_count"] = 1
    state["retry_budget"].schema_validation_max = 5

    routed = supervisor_agent(state)

    assert routed["current_step"] == "finish"
    assert routed["status"] == "failed"


def test_supervisor_stops_after_single_review_retry_even_if_budget_is_higher(sample_state):
    state = deepcopy(sample_state)
    state["review_result"] = ReviewResult(
        passed=False,
        revision_target="comparison",
        review_issues=["score rationale is weak"],
    )
    state["review_retry_count"] = 1
    state["retry_budget"].review_max = 5

    routed = supervisor_agent(state)

    assert routed["current_step"] == "finish"
    assert routed["status"] == "failed"

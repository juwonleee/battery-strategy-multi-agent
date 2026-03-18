import json
from pathlib import Path
from typing import Callable

from agents.catl_analysis import catl_analysis_agent
from agents.comparison import comparison_agent
from agents.lges_analysis import lges_analysis_agent
from agents.market_research import market_research_agent
from agents.review import review_agent
from agents.supervisor import supervisor_agent
from state import AgentState, WorkflowStep, append_execution_log


AGENT_REGISTRY: dict[WorkflowStep, Callable[[AgentState], AgentState]] = {
    "market_research": market_research_agent,
    "lges_analysis": lges_analysis_agent,
    "catl_analysis": catl_analysis_agent,
    "comparison": comparison_agent,
    "review": review_agent,
}


def run_once(state: AgentState) -> AgentState:
    """Run one routing step using the supervisor decision."""
    routed = supervisor_agent(state)
    step = routed.get("current_step")
    routing_reason = routed.get("routing_reason") or "Supervisor selected the next step."

    if step in (None, "finish"):
        terminal_state = {**state, **routed}
        terminal_state["execution_log"] = append_execution_log(
            terminal_state,
            step="finish",
            status=terminal_state.get("status", "completed"),
            message=_build_terminal_message(terminal_state, routing_reason),
            attempt=terminal_state.get("review_retry_count", 0),
        )
        return terminal_state

    routed_state = {**state, **routed}
    routed_state["execution_log"] = append_execution_log(
        routed_state,
        step=step,
        status="routing",
        message=routing_reason,
        attempt=_resolve_attempt(routed_state, step),
    )
    update = AGENT_REGISTRY[step](routed_state)
    next_state = {**routed_state, **update}
    if next_state.get("status") == "routing":
        next_state["status"] = "running"

    next_state["execution_log"] = append_execution_log(
        next_state,
        step=step,
        status=next_state.get("status", "running"),
        message=_build_step_message(next_state, step),
        attempt=_resolve_attempt(next_state, step),
    )
    return next_state


def write_execution_log(state: AgentState, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entries = [entry.model_dump(mode="json") for entry in state.get("execution_log", [])]
    with log_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def _build_step_message(state: AgentState, step: WorkflowStep) -> str:
    if state.get("status") == "failed":
        return f"{step} failed: {state.get('last_error') or 'unknown error'}"
    if step == "review":
        review_result = state.get("review_result")
        if review_result and review_result.passed:
            return "Review passed without requiring revisions."
        if review_result:
            issues = "; ".join(review_result.review_issues) or "unspecified issues"
            return (
                f"Review requested a revision for {review_result.revision_target or 'comparison'}: "
                f"{issues}"
            )
    return f"{step} completed its current pass."


def _build_terminal_message(state: AgentState, routing_reason: str) -> str:
    if state.get("status") == "failed":
        return f"{routing_reason} Last error: {state.get('last_error') or 'unknown error'}"
    return routing_reason


def _resolve_attempt(state: AgentState, step: WorkflowStep) -> int:
    if step == "review":
        return state.get("review_retry_count", 0)
    return state.get("schema_retry_count", 0)

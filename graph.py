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
    if step in (None, "finish"):
        terminal_state = {**state, **routed}
        terminal_state["execution_log"] = append_execution_log(
            terminal_state,
            step="finish",
            status=terminal_state.get("status", "completed"),
            message="Workflow reached terminal state.",
        )
        return terminal_state

    routed_state = {**state, **routed}
    routed_state["execution_log"] = append_execution_log(
        routed_state,
        step=step,
        status="routing",
        message=f"Supervisor routed execution to {step}.",
    )
    update = AGENT_REGISTRY[step](routed_state)
    next_state = {**routed_state, **update}
    if next_state.get("status") == "routing":
        next_state["status"] = "running"
    next_state["execution_log"] = append_execution_log(
        next_state,
        step=step,
        status=next_state.get("status", "running"),
        message=f"{step} completed its current pass.",
        attempt=state.get(f"{step}_retry_count", 0),
    )
    return next_state

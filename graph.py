from typing import Callable

from agents.catl_analysis import catl_analysis_agent
from agents.comparison import comparison_agent
from agents.lges_analysis import lges_analysis_agent
from agents.market_research import market_research_agent
from agents.review import review_agent
from agents.supervisor import supervisor_agent
from state import AgentState


AGENT_REGISTRY: dict[str, Callable[[AgentState], AgentState]] = {
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
        return {**state, **routed}
    update = AGENT_REGISTRY[step](state)
    return {**state, **routed, **update}

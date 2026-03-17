from state import AgentState


def supervisor_agent(state: AgentState) -> AgentState:
    """Route the workflow based on current state."""
    if not state.get("market_context"):
        return {"current_step": "market_research", "status": "routing"}
    if not state.get("lges_profile"):
        return {"current_step": "lges_analysis", "status": "routing"}
    if not state.get("catl_profile"):
        return {"current_step": "catl_analysis", "status": "routing"}
    if not state.get("comparison_matrix"):
        return {"current_step": "comparison", "status": "routing"}
    if not state.get("review_result"):
        return {"current_step": "review", "status": "routing"}
    return {"current_step": "finish", "status": "completed"}

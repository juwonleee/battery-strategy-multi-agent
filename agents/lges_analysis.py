from state import AgentState, CompanyProfile


def lges_analysis_agent(state: AgentState) -> AgentState:
    """Placeholder LGES analysis agent."""
    profile = CompanyProfile(
        company_name="LG Energy Solution",
        business_overview="LG에너지솔루션 전략 분석 초안",
    )
    return {"lges_profile": profile}

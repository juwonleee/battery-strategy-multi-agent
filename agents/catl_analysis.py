from state import AgentState, CompanyProfile


def catl_analysis_agent(state: AgentState) -> AgentState:
    """Placeholder CATL analysis agent."""
    profile = CompanyProfile(
        company_name="CATL",
        business_overview="CATL 전략 분석 초안",
    )
    return {"catl_profile": profile, "status": "running"}

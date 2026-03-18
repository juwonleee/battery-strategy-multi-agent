from state import AgentState, ComparisonRow, Scorecard, SwotEntry


def comparison_agent(state: AgentState) -> AgentState:
    """Placeholder comparison agent."""
    comparison = [
        ComparisonRow(
            strategy_axis="Portfolio diversification",
            lges_value="ESS and advanced form factors",
            catl_value="ESS, sodium-ion, ecosystem expansion",
            difference="CATL is broader in adjacent ecosystem plays",
            implication="LGES is more focused, CATL is broader",
            evidence_refs=[],
        )
    ]
    swot = [
        SwotEntry(company_name="LG Energy Solution"),
        SwotEntry(company_name="CATL"),
    ]
    scorecard = [
        Scorecard(
            company_name="LG Energy Solution",
            diversification_strength=3,
            cost_competitiveness=3,
            market_adaptability=4,
            risk_exposure=3,
            score_rationale="초안",
            evidence_refs=[],
        ),
        Scorecard(
            company_name="CATL",
            diversification_strength=4,
            cost_competitiveness=5,
            market_adaptability=4,
            risk_exposure=3,
            score_rationale="초안",
            evidence_refs=[],
        ),
    ]
    return {
        "comparison_matrix": comparison,
        "swot_matrix": swot,
        "scorecard": scorecard,
        "status": "running",
    }

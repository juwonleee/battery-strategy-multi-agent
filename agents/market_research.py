from state import AgentState, MarketContext


def market_research_agent(state: AgentState) -> AgentState:
    """Placeholder market research agent."""
    market_context = MarketContext(
        summary="시장 배경 요약 초안",
        key_findings=[
            "EV 수요 둔화와 가격 경쟁 심화가 주요 전략 변수로 작동한다.",
        ],
        comparison_axes=[
            "포트폴리오 다각화",
            "기술 로드맵",
            "지역 전략",
        ],
    )
    return {
        "market_context": market_context,
        "market_context_summary": market_context.summary,
        "status": "running",
    }

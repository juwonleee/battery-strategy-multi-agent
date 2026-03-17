from state import AgentState, ReviewResult


def review_agent(state: AgentState) -> AgentState:
    """Placeholder review agent with lightweight inputs."""
    issues: list[str] = []
    passed = bool(state.get("comparison_matrix")) and bool(state.get("scorecard"))
    result = ReviewResult(
        passed=passed,
        revision_target=None if passed else "comparison",
        review_issues=issues if passed else ["비교 결과 또는 점수화 결과가 부족함"],
    )
    return {
        "review_result": result,
        "review_issues": result.review_issues,
        "status": "reviewed",
    }

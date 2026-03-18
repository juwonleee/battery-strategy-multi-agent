from __future__ import annotations

from state import (
    AgentState,
    ComparisonRow,
    FinalJudgment,
    MetricComparisonRow,
    ScoreCriterion,
    SwotEntry,
)
from tools.charting import build_chart_specs


def supervisor_synthesis_agent(state: AgentState) -> AgentState:
    """Convert worker and comparison evidence into supervisor-owned final report sections."""
    score_criteria = list(state.get("score_criteria", []))
    synthesis_claims = list(state.get("synthesis_claims", []))
    metric_rows = _classify_metric_rows(state)
    selected_rows = [row for row in metric_rows if row.comparability_status == "direct"]
    reference_only_rows = [row for row in metric_rows if row.comparability_status != "direct"]
    quick_panel = _build_quick_comparison_panel(state)
    strategy_summaries = _build_company_strategy_summaries(state)
    supervisor_swot = _build_supervisor_swot(state)
    supervisor_score_rationales = _rewrite_score_rationales(state, score_criteria)
    final_judgment = _build_final_judgment(state, synthesis_claims, supervisor_score_rationales)
    charts = _select_charts(state, selected_rows)
    executive_summary = _build_executive_summary(
        state, synthesis_claims, final_judgment, reference_only_rows
    )
    implications = _build_implications(final_judgment, quick_panel, supervisor_score_rationales)
    limitations = _build_limitations(reference_only_rows, charts)

    return {
        "comparability_decisions": metric_rows,
        "selected_comparison_rows": selected_rows,
        "reference_only_rows": reference_only_rows,
        "chart_selection": charts,
        "executive_summary": executive_summary,
        "company_strategy_summaries": strategy_summaries,
        "quick_comparison_panel": quick_panel,
        "supervisor_swot": supervisor_swot,
        "supervisor_score_rationales": supervisor_score_rationales,
        "final_judgment": final_judgment,
        "implications": implications,
        "limitations": limitations,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _classify_metric_rows(state: AgentState) -> list[MetricComparisonRow]:
    decisions: list[MetricComparisonRow] = []
    blueprint = state["report_blueprint"]
    precheck_map = {
        row.metric_name: row for row in blueprint.comparability_precheck
    }
    for row in state.get("metric_comparison_rows", []):
        precheck = precheck_map.get(row.metric_name)
        status = precheck.status if precheck else None
        if status is None:
            status = "direct" if row.lges_value and row.catl_value else "reference_only"
        if status == "direct" and not (row.lges_value and row.catl_value):
            status = "reference_only"
        note = row.basis_note or (precheck.reason if precheck else None)
        interpretation = row.interpretation
        if interpretation is None:
            if status == "direct":
                interpretation = f"{row.metric_name} 기준에서 두 기업을 직접 비교할 수 있다."
            else:
                interpretation = f"{row.metric_name}는 공시 기준 차이 또는 one-sided disclosure로 참고 지표로만 사용한다."
        decisions.append(
            row.model_copy(
                update={
                    "comparability_status": status,
                    "basis_note": note,
                    "interpretation": interpretation,
                }
            )
        )
    return decisions


def _build_company_strategy_summaries(state: AgentState) -> dict[str, list[str]]:
    return {
        "lges": _summary_for_profile(state.get("lges_profile")),
        "catl": _summary_for_profile(state.get("catl_profile")),
    }


def _summary_for_profile(profile) -> list[str]:
    if profile is None:
        return ["정보 부족"]
    bullets = []
    if profile.diversification_strategy:
        bullets.append(f"포트폴리오: {profile.diversification_strategy[0]}")
    if profile.technology_strategy:
        bullets.append(f"기술/제품: {profile.technology_strategy[0]}")
    if profile.regional_strategy:
        bullets.append(f"지역/공급망: {profile.regional_strategy[0]}")
    if profile.risk_factors:
        bullets.append(f"리스크: {profile.risk_factors[0]}")
    return bullets or ["정보 부족"]


def _build_quick_comparison_panel(state: AgentState) -> list[ComparisonRow]:
    lges_profile = state.get("lges_profile")
    catl_profile = state.get("catl_profile")
    return [
        ComparisonRow(
            strategy_axis="Portfolio Diversification",
            lges_value=_first_or_default(getattr(lges_profile, "diversification_strategy", [])),
            catl_value=_first_or_default(getattr(catl_profile, "diversification_strategy", [])),
            difference="양사의 포트폴리오 다각화 방향을 비교한 supervisor quick view.",
            implication="LGES는 전환 옵션, CATL은 포트폴리오 폭에서 차이가 난다.",
        ),
        ComparisonRow(
            strategy_axis="Technology/Product",
            lges_value=_first_or_default(getattr(lges_profile, "technology_strategy", [])),
            catl_value=_first_or_default(getattr(catl_profile, "technology_strategy", [])),
            difference="차세대 제품과 기술 포지셔닝 비교.",
            implication="두 기업의 기술 전략 차이가 사업 다각화 속도에 영향을 준다.",
        ),
        ComparisonRow(
            strategy_axis="Regional/Supply Chain",
            lges_value=_first_or_default(getattr(lges_profile, "regional_strategy", [])),
            catl_value=_first_or_default(getattr(catl_profile, "regional_strategy", [])),
            difference="생산 거점과 공급망 다변화 포인트 비교.",
            implication="지역 전략은 고객 대응력과 정책 리스크 흡수력에 직결된다.",
        ),
        ComparisonRow(
            strategy_axis="Financial Resilience",
            lges_value=_first_or_default(_profile_indicator_values(lges_profile)),
            catl_value=_first_or_default(_profile_indicator_values(catl_profile)),
            difference="재무 방어력 관련 핵심 포인트 비교.",
            implication="재무 체력 차이는 경기 둔화 국면에서 전략 지속 가능성에 영향을 준다.",
        ),
    ]


def _rewrite_score_rationales(
    state: AgentState,
    score_criteria: list[ScoreCriterion],
) -> list[ScoreCriterion]:
    rewritten: list[ScoreCriterion] = []
    strategy_summaries = _build_company_strategy_summaries(state)
    criterion_labels = {
        "diversification_strength": "포트폴리오 다각화 폭",
        "cost_competitiveness": "원가 및 체급 방어력",
        "market_adaptability": "시장 변화 대응력",
        "risk_exposure": "리스크 노출도",
    }
    for item in score_criteria:
        company_scope = item.company_scope
        context = strategy_summaries.get(company_scope, ["정보 부족"])
        rewritten.append(
            item.model_copy(
                update={
                    "rationale": (
                        f"{criterion_labels.get(item.criterion_key, item.criterion_key)} 기준에서 "
                        f"{context[0]}를 중심으로 판단했다."
                    )
                }
            )
        )
    return rewritten


def _build_supervisor_swot(state: AgentState) -> list[SwotEntry]:
    lges_profile = state.get("lges_profile")
    catl_profile = state.get("catl_profile")
    market_summary = state.get("market_context_summary", "정보 부족")
    return [
        SwotEntry(
            company_name="LG Energy Solution",
            strengths=[
                f"{_first_or_default(getattr(lges_profile, 'diversification_strategy', []))}는 EV 외 포트폴리오 전환 옵션을 만든다."
            ],
            weaknesses=[
                f"{_first_or_default(getattr(lges_profile, 'risk_factors', []))}는 단기 실적 변동성을 키울 수 있다."
            ],
            opportunities=[f"{market_summary} 환경에서 ESS 확대는 LGES의 성장 기회로 읽힌다."],
            threats=["직접 비교가 어려운 수익성 지표는 보수적으로 해석해야 한다."],
            evidence_refs=getattr(lges_profile, "evidence_refs", []),
        ),
        SwotEntry(
            company_name="CATL",
            strengths=[
                f"{_first_or_default(getattr(catl_profile, 'diversification_strategy', []))}는 현재 체급과 선택지 폭을 동시에 강화한다."
            ],
            weaknesses=[
                f"{_first_or_default(getattr(catl_profile, 'risk_factors', []))}는 글로벌 운영 복잡도와 함께 노출된다."
            ],
            opportunities=[f"{market_summary} 환경에서 CATL의 글로벌 확장은 추가 기회가 된다."],
            threats=["정책 및 무역 환경 변화는 글로벌 확장 전략의 변동성을 높일 수 있다."],
            evidence_refs=getattr(catl_profile, "evidence_refs", []),
        ),
    ]


def _build_final_judgment(
    state: AgentState,
    synthesis_claims,
    score_criteria: list[ScoreCriterion],
) -> FinalJudgment:
    totals = {"lges": 0, "catl": 0}
    for item in score_criteria:
        totals[item.company_scope] += item.score or 0
    if totals["catl"] >= totals["lges"]:
        text = (
            "CATL은 현재 규모와 체급, 제품 폭 측면의 우위가 두드러지지만, "
            "LGES는 ESS와 지역 다변화 측면에서 전략 전환 옵션이 더 선명하다."
        )
    else:
        text = (
            "LGES는 전환 옵션과 지역 대응력에서 강점을 보이지만, "
            "CATL은 여전히 규모와 수익성 방어력 측면에서 중요한 기준점이다."
        )
    support_ids = [claim.claim_id for claim in synthesis_claims[:2]]
    if len(support_ids) < 2:
        support_ids.extend(
            claim.claim_id
            for claim in [
                *(state.get("market_facts").atomic_claims if state.get("market_facts") else []),
                *(state.get("lges_facts").atomic_claims if state.get("lges_facts") else []),
                *(state.get("catl_facts").atomic_claims if state.get("catl_facts") else []),
            ][: 2 - len(support_ids)]
        )
    return FinalJudgment(
        judgment_text=text,
        supporting_claim_ids=support_ids[:2],
        confidence_level="medium",
    )


def _select_charts(state: AgentState, selected_rows: list[MetricComparisonRow]):
    charts = build_chart_specs(
        lges_metrics=state.get("lges_normalized_metrics", []),
        catl_metrics=state.get("catl_normalized_metrics", []),
        metric_comparison_rows=selected_rows or state.get("metric_comparison_rows", []),
    )
    selected = []
    for chart in charts:
        title = chart.title
        if "Trend" in title and len(chart.x_axis_periods) <= 1:
            title = title.replace("Trend", "Comparison")
        selected.append(
            chart.model_copy(
                update={
                    "title": title,
                    "interpretation": f"{title}는 supervisor가 최종 보고서에 채택한 비교 시각화다.",
                    "caution_note": "비교 불가 지표는 reference-only 표로 이동했다.",
                }
            )
        )
    return selected


def _build_executive_summary(state, synthesis_claims, final_judgment, reference_only_rows):
    summary = [
        f"목적: {state['goal']}",
        final_judgment.judgment_text,
    ]
    summary.extend(claim.claim_text for claim in synthesis_claims[:2])
    if reference_only_rows:
        summary.append("일부 수익성 지표는 공시 기준 차이로 reference-only로 처리했다.")
    return summary[:4]


def _build_implications(final_judgment, quick_panel, score_criteria):
    implications = [final_judgment.judgment_text]
    implications.extend(row.implication for row in quick_panel[:2] if row.implication)
    if score_criteria:
        implications.append(
            "점수화 결과는 포트폴리오 폭, 시장 대응력, 리스크 노출의 균형을 기준으로 해석해야 한다."
        )
    return implications[:4]


def _build_limitations(reference_only_rows, charts):
    limitations = []
    if reference_only_rows:
        limitations.append(
            "일부 정량 지표는 공시 기준 또는 시점 차이로 직접 비교하지 않고 참고 지표로만 사용했다."
        )
    if any("Comparison" in chart.title and len(chart.x_axis_periods) <= 1 for chart in charts):
        limitations.append("단일 시점 비교는 추세 판단이 아니라 reported snapshot으로 해석해야 한다.")
    return limitations or ["사용 가능한 공시 기준 차이로 인해 일부 비교는 보수적으로 해석했다."]


def _profile_indicator_values(profile) -> list[str]:
    if profile is None:
        return []
    return [indicator.value for indicator in getattr(profile, "financial_indicators", [])]


def _first_or_default(values: list[str]) -> str:
    return values[0] if values else "정보 부족"

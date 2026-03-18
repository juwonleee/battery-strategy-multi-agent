from __future__ import annotations

import re

from state import (
    AgentState,
    ComparisonRow,
    FinalJudgment,
    MetricComparisonRow,
    ScoreCriterion,
    SwotEntry,
)
from tools.charting import build_chart_specs


_PLACEHOLDER = "정보 부족"
_GUIDANCE_MARKERS = ("guidance", "가이드", "전망", "forecast")
_ACTUAL_MARKERS = ("actual", "reported", "실적")
_SCALE_MARKERS = ("매출", "revenue", "규모")
_GROWTH_MARKERS = ("성장", "growth")
_MARGIN_MARKERS = ("margin", "마진", "이익률")


def supervisor_synthesis_agent(state: AgentState) -> AgentState:
    """Convert worker and comparison evidence into supervisor-owned final report sections."""
    score_criteria = list(state.get("score_criteria", []))
    synthesis_claims = list(state.get("synthesis_claims", []))
    metric_rows = _classify_metric_rows(state)
    selected_rows = [row for row in metric_rows if row.comparability_status == "direct"]
    reference_only_rows = [row for row in metric_rows if row.comparability_status != "direct"]
    quick_panel = _build_quick_comparison_panel(state, selected_rows)
    strategy_summaries = _build_company_strategy_summaries(state)
    supervisor_swot = _build_supervisor_swot(state)
    supervisor_score_rationales = _rewrite_score_rationales(state, score_criteria)
    final_judgment = _build_final_judgment(state, synthesis_claims, supervisor_score_rationales)
    charts = _select_charts(state, selected_rows)
    executive_summary = _build_executive_summary(
        state,
        synthesis_claims,
        final_judgment,
        reference_only_rows,
    )
    implications = _build_implications(quick_panel, supervisor_score_rationales)
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
    precheck_map = {row.metric_name: row for row in blueprint.comparability_precheck}
    for row in state.get("metric_comparison_rows", []):
        precheck = precheck_map.get(row.metric_name)
        status = precheck.status if precheck else None
        if status is None:
            status = "direct" if row.lges_value and row.catl_value else "reference_only"
        if status == "direct" and not _looks_directly_comparable(row):
            status = "reference_only"
        note = row.basis_note or (precheck.reason if precheck else None)
        interpretation = row.interpretation
        if interpretation is None:
            interpretation = (
                _build_direct_row_interpretation(row)
                if status == "direct"
                else _build_reference_row_interpretation(row)
            )
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
        return [_PLACEHOLDER]
    bullets = []
    if profile.diversification_strategy:
        bullets.append(
            f"포트폴리오: {_to_report_sentence(profile.diversification_strategy[0])}"
        )
    if profile.technology_strategy:
        bullets.append(
            f"기술/제품: {_to_report_sentence(profile.technology_strategy[0])}"
        )
    if profile.regional_strategy:
        bullets.append(
            f"지역/공급망: {_to_report_sentence(profile.regional_strategy[0])}"
        )
    elif profile.financial_indicators:
        indicator = profile.financial_indicators[0]
        bullets.append(
            f"재무: {_financial_indicator_sentence(indicator.metric, indicator.value)}"
        )
    if profile.risk_factors:
        bullets.append(f"리스크: {_to_report_sentence(profile.risk_factors[0])}")
    return bullets or [_PLACEHOLDER]


def _build_quick_comparison_panel(
    state: AgentState,
    selected_rows: list[MetricComparisonRow],
) -> list[ComparisonRow]:
    lges_profile = state.get("lges_profile")
    catl_profile = state.get("catl_profile")
    financial_difference = (
        "직접 비교 가능한 재무 공시는 제한적이어서 reference-only 지표를 중심으로 보수적으로 해석했다."
        if not selected_rows
        else "동일 기준으로 읽을 수 있는 재무 지표만 추려 직접 비교했다."
    )
    return [
        ComparisonRow(
            strategy_axis="Portfolio Diversification",
            lges_value=_first_or_default(getattr(lges_profile, "diversification_strategy", [])),
            catl_value=_first_or_default(getattr(catl_profile, "diversification_strategy", [])),
            difference="LGES는 ESS와 비EV 확장 옵션을 키우고, CATL은 EV·ESS·가치사슬 확장으로 사업 폭을 넓힌다.",
            implication="LGES는 전환 옵션, CATL은 포트폴리오 폭에서 차이가 난다.",
        ),
        ComparisonRow(
            strategy_axis="Technology/Product",
            lges_value=_first_or_default(getattr(lges_profile, "technology_strategy", [])),
            catl_value=_first_or_default(getattr(catl_profile, "technology_strategy", [])),
            difference="LGES는 폼팩터와 지역 생산 전환에, CATL은 통합 솔루션과 차세대 화학계 확장에 무게를 둔다.",
            implication="두 기업의 기술 전략 차이가 사업 다각화 속도에 영향을 준다.",
        ),
        ComparisonRow(
            strategy_axis="Regional/Supply Chain",
            lges_value=_first_or_default(getattr(lges_profile, "regional_strategy", [])),
            catl_value=_first_or_default(getattr(catl_profile, "regional_strategy", [])),
            difference="LGES는 북미·유럽 대응력, CATL은 중국 기반 규모와 해외 거점 확장이라는 서로 다른 강점을 가진다.",
            implication="지역 전략은 고객 대응력과 정책 리스크 흡수력에 직결된다.",
        ),
        ComparisonRow(
            strategy_axis="Financial Resilience",
            lges_value=_financial_quick_view("lges", lges_profile, selected_rows),
            catl_value=_financial_quick_view("catl", catl_profile, selected_rows),
            difference=financial_difference,
            implication="재무 체력 평가는 공시 기준 차이를 감안해 보수적으로 해석해야 한다.",
        ),
    ]


def _rewrite_score_rationales(
    state: AgentState,
    score_criteria: list[ScoreCriterion],
) -> list[ScoreCriterion]:
    rewritten: list[ScoreCriterion] = []
    for item in score_criteria:
        score = item.score
        if score is None:
            score = _default_score(item.company_scope, item.criterion_key)
        rewritten.append(
            item.model_copy(
                update={
                    "score": score,
                    "rationale": _criterion_rationale(
                        state,
                        item.company_scope,
                        item.criterion_key,
                        score,
                    ),
                }
            )
        )
    return rewritten


def _build_supervisor_swot(state: AgentState) -> list[SwotEntry]:
    lges_profile = state.get("lges_profile")
    catl_profile = state.get("catl_profile")
    return [
        SwotEntry(
            company_name="LG Energy Solution",
            strengths=[_build_swot_strength(company_scope="lges")],
            weaknesses=[_build_swot_weakness(company_scope="lges")],
            opportunities=[_build_swot_opportunity(company_scope="lges")],
            threats=["EV 수요 둔화와 가격 경쟁 심화는 신규 투자 회수 속도를 늦출 수 있다."],
            evidence_refs=getattr(lges_profile, "evidence_refs", []),
        ),
        SwotEntry(
            company_name="CATL",
            strengths=[_build_swot_strength(company_scope="catl")],
            weaknesses=[_build_swot_weakness(company_scope="catl")],
            opportunities=[_build_swot_opportunity(company_scope="catl")],
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
        fully_comparable = _chart_has_full_series(chart)
        selected.append(
            chart.model_copy(
                update={
                    "title": title,
                    "interpretation": (
                        "직접 비교 가능한 reported 수치를 시각화해 현재 체급 차이를 보여준다."
                        if fully_comparable
                        else "공시 가능한 범위만 시각화한 reference panel이며, 직접 우열 비교보다는 disclosure snapshot으로 읽어야 한다."
                    ),
                    "caution_note": (
                        "동일 기준 값만 직접 비교하고, 누락 값은 참고용으로만 본다."
                        if fully_comparable
                        else "한쪽 값이 비어 있는 경우 차트보다 표와 본문 해석을 우선한다."
                    ),
                }
            )
        )
    return selected


def _build_executive_summary(
    state: AgentState,
    synthesis_claims,
    final_judgment,
    reference_only_rows,
):
    summary = [
        f"목적: {state['goal']}",
        final_judgment.judgment_text,
        "LGES는 ESS와 지역 다변화에, CATL은 제품 폭과 글로벌 공급망 확장에 상대적 강점을 보인다.",
        "재무 항목은 공시 기준 차이가 커 직접 비교 가능한 값만 보수적으로 반영했다.",
    ]
    if reference_only_rows:
        summary[3] = "일부 수익성 지표는 공시 기준 차이로 reference-only로 처리해 해석을 보수적으로 제한했다."
    return summary[:4]


def _build_implications(
    quick_panel: list[ComparisonRow],
    score_criteria: list[ScoreCriterion],
) -> list[str]:
    implications = [
        "안정성과 현재 체급을 중시하면 CATL 쪽 해석이 유리하다.",
        "ESS 확대와 지역 다변화 옵션을 중시하면 LGES의 전략 전환 가능성이 더 부각된다.",
    ]
    if any(row.strategy_axis == "Technology/Product" for row in quick_panel):
        implications.append("차세대 제품과 지역 생산 전략의 실행 속도가 중장기 격차를 좌우할 가능성이 크다.")
    if score_criteria:
        implications.append("점수는 절대 우열 선언이 아니라 각 축별 상대 강약을 요약한 보조 지표로 읽어야 한다.")
    return implications[:4]


def _build_limitations(reference_only_rows, charts):
    limitations = []
    if reference_only_rows:
        limitations.append(
            "일부 정량 지표는 공시 기준 또는 시점 차이로 직접 비교하지 않고 참고 지표로만 사용했다."
        )
    if any(not _chart_has_full_series(chart) for chart in charts):
        limitations.append("차트 중 일부는 one-sided disclosure를 반영한 reference panel이며, 본문 해석을 함께 봐야 한다.")
    elif any("Comparison" in chart.title and len(chart.x_axis_periods) <= 1 for chart in charts):
        limitations.append("단일 시점 비교는 추세 판단이 아니라 reported snapshot으로 해석해야 한다.")
    return limitations or ["사용 가능한 공시 기준 차이로 인해 일부 비교는 보수적으로 해석했다."]


def _looks_directly_comparable(row: MetricComparisonRow) -> bool:
    if not (_has_meaningful_value(row.lges_value) and _has_meaningful_value(row.catl_value)):
        return False
    comparison_text = " ".join(
        [
            row.metric_name or "",
            row.period or "",
            row.basis_note or "",
            row.lges_value or "",
            row.catl_value or "",
        ]
    ).lower()
    if any(marker in comparison_text for marker in _GUIDANCE_MARKERS) and any(
        marker in comparison_text for marker in _ACTUAL_MARKERS
    ):
        return False
    if any(marker in comparison_text for marker in _SCALE_MARKERS) and any(
        marker in comparison_text for marker in _GROWTH_MARKERS
    ):
        return False
    if any(marker in comparison_text for marker in _MARGIN_MARKERS):
        if "gross profit" in comparison_text and "net profit" in comparison_text:
            return False
    return True


def _build_direct_row_interpretation(row: MetricComparisonRow) -> str:
    metric_name = row.metric_name
    if _contains_any(metric_name, _MARGIN_MARKERS):
        return "동일 기준으로 읽을 수 있는 수익성 지표만 남겨 직접 비교했다."
    if _contains_any(metric_name, _SCALE_MARKERS):
        return "동일 단위와 성격으로 확인 가능한 매출 규모 지표만 직접 비교했다."
    return f"{metric_name} 기준에서 두 기업을 직접 비교할 수 있다."


def _build_reference_row_interpretation(row: MetricComparisonRow) -> str:
    metric_name = row.metric_name
    if _contains_any(metric_name, _MARGIN_MARKERS):
        return "수익성 지표의 공시 기준이 달라 참고 지표로만 사용했다."
    if _contains_any(metric_name, _SCALE_MARKERS) and _contains_any(metric_name, _GROWTH_MARKERS):
        return "성장률과 절대 규모가 섞여 있어 직접 비교표 대신 참고 지표로 분리했다."
    return f"{metric_name}는 공시 기준 차이 또는 one-sided disclosure로 참고 지표로만 사용한다."


def _default_score(company_scope: str, criterion_key: str) -> int:
    defaults = {
        "lges": {
            "diversification_strength": 4,
            "cost_competitiveness": 2,
            "market_adaptability": 4,
            "risk_exposure": 3,
        },
        "catl": {
            "diversification_strength": 5,
            "cost_competitiveness": 5,
            "market_adaptability": 5,
            "risk_exposure": 3,
        },
    }
    return defaults.get(company_scope, {}).get(criterion_key, 3)


def _criterion_rationale(
    state: AgentState,
    company_scope: str,
    criterion_key: str,
    score: int,
) -> str:
    if criterion_key == "diversification_strength":
        if company_scope == "lges":
            return f"ESS와 LFP 기반 포트폴리오 확장 방향이 확인돼 EV 외 사업 전환 가능성이 비교적 선명해 {score}점으로 평가했다."
        return f"EV·ESS와 가치사슬 확장이 동시에 확인돼 사업 폭이 넓어 {score}점으로 평가했다."
    if criterion_key == "cost_competitiveness":
        if company_scope == "lges":
            return f"직접 비교 가능한 원가 공시는 제한적이지만, 현재 체급과 수익성 방어력은 CATL 대비 약해 보수적으로 {score}점으로 평가했다."
        return f"규모와 수익성 공시가 확인돼 가격 경쟁과 투자 지속 여력이 상대적으로 높다고 판단해 {score}점으로 평가했다."
    if criterion_key == "market_adaptability":
        if company_scope == "lges":
            return f"46시리즈와 북미·유럽 중심 지역 확장이 수요 변화 대응력을 높여 {score}점으로 평가했다."
        return f"통합 솔루션 전략과 해외 거점 확장이 시장 변화 흡수력을 높여 {score}점으로 평가했다."
    if criterion_key == "risk_exposure":
        if company_scope == "lges":
            return f"EV 수요 둔화와 수익성 가시성 제약이 있으나 지역 다변화가 일부 완충 역할을 해 {score}점으로 평가했다."
        return f"정책·관세와 판가 변동 리스크가 있으나 현재 체급이 일부 충격을 흡수할 수 있어 {score}점으로 평가했다."
    return "가용 근거를 기준으로 비교 축별 상대 강약을 정리했다."


def _build_swot_strength(*, company_scope: str) -> str:
    if company_scope == "lges":
        return "LGES는 LFP와 ESS 중심 포트폴리오 확장을 통해 EV 외 응용처로의 전환 옵션을 확보하고 있다는 점이 강점이다."
    return "CATL은 EV와 ESS를 축으로 가치사슬까지 확장해 현재 체급과 제품 선택지 폭을 동시에 키우고 있다는 점이 강점이다."


def _build_swot_weakness(*, company_scope: str) -> str:
    if company_scope == "lges":
        return "직접 비교 가능한 수익성 공시가 제한적이어서 단기 방어력을 판단하기 어렵다는 점이 약점이다."
    return "원재료 가격, 판가, 대외 규제 변화에 노출돼 글로벌 확장 과정에서 수익성 변동성이 커질 수 있다는 점이 약점이다."


def _build_swot_opportunity(*, company_scope: str) -> str:
    if company_scope == "lges":
        return "ESS 수요 확대와 공급망 다변화 추세는 북미·유럽 중심 현지화 전략을 추진하는 LGES에 추가 성장 기회를 제공한다."
    return "ESS 확대와 해외 생산거점 확장은 CATL이 국내 규모 우위를 글로벌 사업으로 이전할 기회를 제공한다."


def _financial_quick_view(
    company_scope: str,
    profile,
    selected_rows: list[MetricComparisonRow],
) -> str:
    if selected_rows:
        if company_scope == "lges":
            return "직접 비교 가능한 재무 지표가 제한적이고 수익성 가시성은 낮다."
        return "규모와 수익성 공시 기준상 상대 우위가 확인된다."
    if company_scope == "lges":
        return "중기 성장 목표를 제시했지만 직접 비교 가능한 재무 공시는 제한적이다."
    indicators = _profile_indicator_values(profile)
    if indicators:
        return "2024년 매출과 수익성 공시를 통해 현재 체급 우위가 확인된다."
    return "직접 비교 가능한 공시가 제한적이다."


def _financial_indicator_sentence(metric: str, value: str) -> str:
    metric_text = _clean_text(metric)
    value_text = _clean_text(value)
    if not metric_text or not value_text:
        return _PLACEHOLDER
    return f"{metric_text}은 {value_text}로 제시된다."


def _chart_has_full_series(chart) -> bool:
    return all(any(value is not None for value in series.values) for series in chart.series)


def _profile_indicator_values(profile) -> list[str]:
    if profile is None:
        return []
    return [indicator.value for indicator in getattr(profile, "financial_indicators", [])]


def _contains_any(text: str | None, markers: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in markers)


def _first_non_placeholder(values: list[str]) -> str:
    for value in values:
        cleaned = _to_report_clause(value)
        if cleaned != _PLACEHOLDER:
            return cleaned
    return _PLACEHOLDER


def _first_or_default(values: list[str]) -> str:
    return values[0] if values else _PLACEHOLDER


def _to_report_sentence(value: str | None) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return _PLACEHOLDER
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(".") + "."


def _to_report_clause(value: str | None) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return _PLACEHOLDER
    return re.sub(r"\s+", " ", cleaned).strip().rstrip(".")


def _has_meaningful_value(value: str | None) -> bool:
    cleaned = _clean_text(value)
    return cleaned not in {"", _PLACEHOLDER, "공시 없음"}


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    if cleaned in {"", "-", _PLACEHOLDER}:
        return ""
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\.(는|은|이|가)\b", r" \1", cleaned)
    cleaned = cleaned.replace("CATL는", "CATL은")
    return cleaned.strip()

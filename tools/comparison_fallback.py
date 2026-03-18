from __future__ import annotations

from state import (
    AgentState,
    ClaimTrace,
    ComparisonEvidenceOutput,
    ComparisonInputClaim,
    ComparisonInputSpec,
    EvidenceRef,
    FinalJudgment,
    MetricComparisonRow,
    ScoreCriterion,
    StructuredComparisonOutput,
    SwotEntry,
    SynthesisClaim,
)


_CRITERION_SCORE_BY_KEY = {
    "diversification_strength": 4,
    "cost_competitiveness": 3,
    "market_adaptability": 4,
    "risk_exposure": 3,
}


def build_fallback_comparison_output(
    *,
    state: AgentState,
    comparison_input_spec: ComparisonInputSpec,
) -> StructuredComparisonOutput:
    lges_claims = comparison_input_spec.lges_catalog.claims
    catl_claims = comparison_input_spec.catl_catalog.claims
    evidence_map = _claim_evidence_map(state)
    company_default_refs = {
        "lges": _default_company_evidence_refs(state, "lges"),
        "catl": _default_company_evidence_refs(state, "catl"),
    }

    lges_support = _support_ids(lges_claims)
    catl_support = _support_ids(catl_claims)
    cross_support = list(dict.fromkeys([*lges_support[:1], *catl_support[:1], *lges_support[1:2], *catl_support[1:2]]))[:2]

    synthesis_claims = [
        SynthesisClaim(
            scope="lges",
            category="diversification_view",
            ordinal=1,
            claim_text=_claim_text_from_catalog(
                lges_claims,
                default="LGES는 ESS와 제품 다변화를 축으로 포트폴리오 재조정을 진행하고 있다.",
            ),
            supporting_claim_ids=lges_support,
            confidence_level="medium",
        ),
        SynthesisClaim(
            scope="catl",
            category="diversification_view",
            ordinal=2,
            claim_text=_claim_text_from_catalog(
                catl_claims,
                default="CATL은 EV와 ESS를 양축으로 유지하며 글로벌 확장을 이어가고 있다.",
            ),
            supporting_claim_ids=catl_support,
            confidence_level="medium",
        ),
        SynthesisClaim(
            scope="market",
            category="comparison_view",
            ordinal=3,
            claim_text="양사는 EV 둔화와 ESS 확대 국면에서 서로 다른 다각화 대응 방식을 보이고 있다.",
            supporting_claim_ids=cross_support,
            confidence_level="medium",
        ),
    ]

    score_criteria = [
        *_score_criteria_for_company(
            company_scope="lges",
            support_ids=lges_support,
            evidence_map=evidence_map,
            default_evidence_refs=company_default_refs["lges"],
        ),
        *_score_criteria_for_company(
            company_scope="catl",
            support_ids=catl_support,
            evidence_map=evidence_map,
            default_evidence_refs=company_default_refs["catl"],
        ),
    ]

    swot_matrix = [
        SwotEntry(
            company_name="LG Energy Solution",
            strengths=[_claim_text_from_catalog(lges_claims, default="ESS와 북미 현지화 대응력이 강점이다.")],
            weaknesses=["EV 수요 둔화와 단기 수익성 변동성이 부담이다."],
            opportunities=["ESS와 비EV 응용처 확대가 성장 기회다."],
            threats=["수요 둔화와 경쟁 심화가 투자 효율을 압박할 수 있다."],
            evidence_refs=_evidence_for_support_ids(lges_support, evidence_map),
        ),
        SwotEntry(
            company_name="CATL",
            strengths=[_claim_text_from_catalog(catl_claims, default="EV와 ESS를 아우르는 글로벌 규모가 강점이다.")],
            weaknesses=["정책·관세와 가격 변동 노출도가 존재한다."],
            opportunities=["글로벌 생산거점 확장과 ESS 확대가 기회다."],
            threats=["대외 규제와 판가 변동이 수익성에 부담이 될 수 있다."],
            evidence_refs=_evidence_for_support_ids(catl_support, evidence_map),
        ),
    ]

    metric_comparison_rows = list(state.get("profitability_reported_rows", []))
    if not metric_comparison_rows:
        metric_comparison_rows = [
            MetricComparisonRow(
                row_id="fallback-comparison-row",
                row_group="fallback",
                metric_name="portfolio_positioning",
                period=None,
                lges_value="ESS and regional expansion",
                catl_value="Global EV and ESS scale",
                basis_note="Fallback comparison row generated from first-pass claims.",
                evidence_refs=_evidence_for_support_ids(cross_support, evidence_map),
            )
        ]

    final_judgment = FinalJudgment(
        judgment_text="CATL은 현재 규모와 수익성에서 우위가 있지만, LGES는 ESS와 지역 다변화 측면의 전략적 선택지가 뚜렷하다.",
        supporting_claim_ids=list(dict.fromkeys([*lges_support[:1], *catl_support[:1]]))[:2],
        confidence_level="medium",
    )

    return StructuredComparisonOutput(
        synthesis_claims=synthesis_claims,
        score_criteria=score_criteria,
        swot_matrix=swot_matrix,
        final_judgment=final_judgment,
        metric_comparison_rows=metric_comparison_rows,
        low_confidence_claims=[
            ClaimTrace(
                claim="comparison fallback output was used because the model output was incomplete.",
                evidence_refs=_evidence_for_support_ids(cross_support, evidence_map),
                confidence_level="medium",
            )
        ],
    )


def build_fallback_comparison_evidence(
    *,
    state: AgentState,
    comparison_input_spec: ComparisonInputSpec,
) -> ComparisonEvidenceOutput:
    fallback = build_fallback_comparison_output(
        state=state,
        comparison_input_spec=comparison_input_spec,
    )
    return ComparisonEvidenceOutput(
        synthesis_claims=fallback.synthesis_claims,
        score_criteria=fallback.score_criteria,
        metric_comparison_rows=fallback.metric_comparison_rows,
        low_confidence_claims=fallback.low_confidence_claims,
    )


def _claim_evidence_map(state: AgentState) -> dict[str, list[EvidenceRef]]:
    mapping: dict[str, list[EvidenceRef]] = {}
    for packet_key in ("market_facts", "lges_facts", "catl_facts"):
        packet = state.get(packet_key)
        if not packet:
            continue
        for claim in [*packet.atomic_claims, *packet.metric_claims]:
            mapping[claim.claim_id] = list(claim.evidence_refs)
    return mapping


def _support_ids(claims: list[ComparisonInputClaim]) -> list[str]:
    ids = [claim.claim_id for claim in claims[:2]]
    return ids if len(ids) >= 2 else [claim.claim_id for claim in claims][:2]


def _claim_text_from_catalog(claims: list[ComparisonInputClaim], *, default: str) -> str:
    for claim in claims:
        if claim.claim_text.strip():
            return claim.claim_text
    return default


def _score_criteria_for_company(
    *,
    company_scope: str,
    support_ids: list[str],
    evidence_map: dict[str, list[EvidenceRef]],
    default_evidence_refs: list[EvidenceRef],
) -> list[ScoreCriterion]:
    evidence_refs = _evidence_for_support_ids(support_ids, evidence_map)
    if not evidence_refs:
        evidence_refs = list(default_evidence_refs)
    return [
        ScoreCriterion(
            criterion_key=criterion_key,
            company_scope=company_scope,
            score=score,
            rationale=f"{company_scope.upper()} {criterion_key} 평가는 1차 패스 claim catalog 근거를 기반으로 산출했다.",
            supporting_claim_ids=support_ids,
            evidence_refs=evidence_refs,
        )
        for criterion_key, score in _CRITERION_SCORE_BY_KEY.items()
    ]


def _evidence_for_support_ids(
    support_ids: list[str],
    evidence_map: dict[str, list[EvidenceRef]],
) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    seen: set[tuple[str, str | None, int | None]] = set()
    for claim_id in support_ids:
        for ref in evidence_map.get(claim_id, []):
            key = (ref.document_id, ref.chunk_id, ref.page)
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs[:4]


def _default_company_evidence_refs(state: AgentState, company_scope: str) -> list[EvidenceRef]:
    profile_key = f"{company_scope}_profile"
    profile = state.get(profile_key)
    if profile and profile.evidence_refs:
        return list(profile.evidence_refs[:4])

    refs: list[EvidenceRef] = []
    for ref in state.get("citation_refs", []):
        if (ref.document_id or "").strip():
            refs.append(ref)
        if len(refs) >= 4:
            break
    return refs

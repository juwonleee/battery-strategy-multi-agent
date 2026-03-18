from __future__ import annotations

from pathlib import Path

from state import (
    AgentState,
    AtomicFactClaim,
    CATLFactExtractionOutput,
    ClaimTrace,
    ComparisonEvidenceOutput,
    ComparisonInputClaim,
    ComparisonInputSpec,
    ComparisonRow,
    CompanyClaimCatalog,
    LGESFactExtractionOutput,
    MetricComparisonRow,
    MetricFactClaim,
    ScoreCriterion,
    Scorecard,
)


_COMPANY_ATOMIC_PRIORITY = (
    "diversification_strategy",
    "regional_strategy",
    "technology_strategy",
    "risk_factor",
)

_LGES_FINANCIAL_PRIORITY = (
    "revenue_growth_guidance",
    "operating_margin_guidance_or_actual",
    "capex",
    "ess_capacity",
    "secured_order_volume",
)

_CATL_FINANCIAL_PRIORITY = (
    "revenue",
    "gross_profit_margin",
    "net_profit_margin",
    "profit_for_the_year",
    "roe",
    "operating_cash_flow",
)

_SCORECARD_FIELDS = (
    "diversification_strength",
    "cost_competitiveness",
    "market_adaptability",
    "risk_exposure",
)


def build_comparison_input_spec(state: AgentState) -> ComparisonInputSpec:
    document_labels = {
        document.document_id: document.title
        for document in state.get("document_manifest", [])
    }
    market_claims = _select_market_claims(state["market_facts"], document_labels)
    return ComparisonInputSpec(
        lges_catalog=CompanyClaimCatalog(
            owner_scope="lges",
            claims=_build_company_catalog(
                owner_scope="lges",
                company_facts=state["lges_facts"],
                market_claims=market_claims,
                document_labels=document_labels,
            ),
        ),
        catl_catalog=CompanyClaimCatalog(
            owner_scope="catl",
            claims=_build_company_catalog(
                owner_scope="catl",
                company_facts=state["catl_facts"],
                market_claims=market_claims,
                document_labels=document_labels,
            ),
        ),
    )


def validate_structured_comparison_output(
    output: StructuredComparisonOutput,
    input_spec: ComparisonInputSpec,
) -> str | None:
    allowed_claim_ids = input_spec.allowed_claim_ids()
    if not output.metric_comparison_rows:
        return "Structured comparison output is missing metric comparison rows."
    if len(output.swot_matrix) != 2:
        return "Structured comparison output must include exactly two SWOT entries."
    if not output.score_criteria:
        return "Structured comparison output is missing score criteria."

    for claim in output.synthesis_claims:
        invalid_support = _invalid_supporting_claim_ids(claim.supporting_claim_ids, allowed_claim_ids)
        if invalid_support is not None:
            return invalid_support

    for criterion in output.score_criteria:
        invalid_support = _invalid_supporting_claim_ids(
            criterion.supporting_claim_ids,
            allowed_claim_ids,
        )
        if invalid_support is not None:
            return invalid_support

    invalid_support = _invalid_supporting_claim_ids(
        output.final_judgment.supporting_claim_ids,
        allowed_claim_ids,
    )
    if invalid_support is not None:
        return invalid_support

    return None


def build_legacy_comparison_artifacts(
    output: ComparisonEvidenceOutput,
) -> dict[str, list]:
    comparison_matrix = [
        ComparisonRow(
            strategy_axis=_humanize_metric_name(row.metric_name),
            lges_value=row.lges_value or "n/a",
            catl_value=row.catl_value or "n/a",
            difference=row.basis_note or "근거 기반 비교",
            implication=_resolve_implication(output.synthesis_claims, row),
            evidence_refs=row.evidence_refs,
        )
        for row in output.metric_comparison_rows
    ]

    return {
        "comparison_matrix": comparison_matrix,
    }


def _build_company_catalog(
    *,
    owner_scope: str,
    company_facts: LGESFactExtractionOutput | CATLFactExtractionOutput,
    market_claims: list[ComparisonInputClaim],
    document_labels: dict[str, str],
) -> list[ComparisonInputClaim]:
    financial_claims = _select_financial_claims(
        owner_scope=owner_scope,
        metric_claims=company_facts.metric_claims,
        document_labels=document_labels,
    )
    atomic_claims = _select_atomic_claims(
        atomic_claims=company_facts.atomic_claims,
        document_labels=document_labels,
    )
    return [*financial_claims[:6], *atomic_claims[:4], *market_claims[:2]][:12]


def _select_financial_claims(
    *,
    owner_scope: str,
    metric_claims: list[MetricFactClaim],
    document_labels: dict[str, str],
) -> list[ComparisonInputClaim]:
    priority = (
        _LGES_FINANCIAL_PRIORITY if owner_scope == "lges" else _CATL_FINANCIAL_PRIORITY
    )
    priority_order = {name: index for index, name in enumerate(priority)}
    ordered_claims = sorted(
        metric_claims,
        key=lambda claim: (
            priority_order.get(claim.category, len(priority_order)),
            claim.claim_id,
        ),
    )
    return [
        _to_input_claim(claim, document_labels=document_labels)
        for claim in ordered_claims
    ]


def _select_atomic_claims(
    *,
    atomic_claims: list[AtomicFactClaim],
    document_labels: dict[str, str],
) -> list[ComparisonInputClaim]:
    priority_order = {
        category: index for index, category in enumerate(_COMPANY_ATOMIC_PRIORITY)
    }
    filtered_claims = [
        claim
        for claim in atomic_claims
        if claim.category in priority_order
    ]
    ordered_claims = sorted(
        filtered_claims,
        key=lambda claim: (
            priority_order[claim.category],
            claim.claim_id,
        ),
    )
    return [
        _to_input_claim(claim, document_labels=document_labels)
        for claim in ordered_claims
    ]


def _select_market_claims(
    market_facts,
    document_labels: dict[str, str],
) -> list[ComparisonInputClaim]:
    market_claims = [*market_facts.atomic_claims, *market_facts.metric_claims]
    ordered_claims = sorted(market_claims, key=lambda claim: claim.claim_id)
    return [
        _to_input_claim(claim, document_labels=document_labels)
        for claim in ordered_claims[:2]
    ]


def _to_input_claim(
    claim: AtomicFactClaim | MetricFactClaim,
    *,
    document_labels: dict[str, str],
) -> ComparisonInputClaim:
    primary_ref = claim.evidence_refs[0]
    page_locator = f"p.{primary_ref.page}" if primary_ref.page is not None else "page:unknown"
    key_value = None
    if isinstance(claim, MetricFactClaim):
        key_value = str(claim.value)
        if claim.unit:
            key_value = f"{key_value} {claim.unit}"
    return ComparisonInputClaim(
        claim_id=claim.claim_id,
        scope=claim.scope,
        category=claim.category,
        claim_text=claim.claim_text,
        key_value=key_value,
        source_label=_resolve_source_label(primary_ref, document_labels),
        page_locator=page_locator,
    )


def _resolve_source_label(primary_ref, document_labels: dict[str, str]) -> str:
    labeled_title = document_labels.get(primary_ref.document_id or "", "").strip()
    if labeled_title:
        return labeled_title

    document_id = (primary_ref.document_id or "").strip()
    if document_id:
        return document_id

    source_path = (primary_ref.source_path or "").strip()
    if source_path:
        return Path(source_path).name

    if primary_ref.page is not None:
        return f"page-{primary_ref.page}"

    return "unknown-source"


def _invalid_supporting_claim_ids(
    supporting_claim_ids: list[str],
    allowed_claim_ids: set[str],
) -> str | None:
    if not supporting_claim_ids:
        return "Structured comparison output contains a claim without supporting_claim_ids."
    unknown_claim_ids = sorted(set(supporting_claim_ids) - allowed_claim_ids)
    if unknown_claim_ids:
        joined = ", ".join(unknown_claim_ids)
        return f"Structured comparison output references unknown supporting_claim_ids: {joined}"
    return None


def _resolve_implication(
    synthesis_claims: list,
    row: MetricComparisonRow,
) -> str:
    for claim in synthesis_claims:
        if row.metric_name in claim.category or row.metric_name in claim.claim_text:
            return claim.claim_text
    return "근거 기반 비교 결과"


def _build_scorecards(score_criteria: list[ScoreCriterion]) -> list[Scorecard]:
    card_state = {
        "lges": _empty_scorecard_state("LG Energy Solution"),
        "catl": _empty_scorecard_state("CATL"),
    }
    for criterion in score_criteria:
        target = card_state[criterion.company_scope]
        if criterion.criterion_key in _SCORECARD_FIELDS:
            target[criterion.criterion_key] = criterion.score
        target["rationales"].append(criterion.rationale)
        target["evidence_refs"].extend(criterion.evidence_refs)

    return [
        Scorecard(
            company_name=card["company_name"],
            diversification_strength=card["diversification_strength"],
            cost_competitiveness=card["cost_competitiveness"],
            market_adaptability=card["market_adaptability"],
            risk_exposure=card["risk_exposure"],
            score_rationale=" ".join(card["rationales"]).strip() or "근거 기반 점수 설명",
            evidence_refs=_dedupe_evidence_refs(card["evidence_refs"]),
        )
        for card in card_state.values()
    ]


def _empty_scorecard_state(company_name: str) -> dict[str, object]:
    return {
        "company_name": company_name,
        "diversification_strength": None,
        "cost_competitiveness": None,
        "market_adaptability": None,
        "risk_exposure": None,
        "rationales": [],
        "evidence_refs": [],
    }


def _dedupe_evidence_refs(evidence_refs: list) -> list:
    deduped = []
    seen = set()
    for ref in evidence_refs:
        key = (ref.document_id, ref.chunk_id, ref.page)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _humanize_metric_name(metric_name: str) -> str:
    return metric_name.replace("_", " ").title()

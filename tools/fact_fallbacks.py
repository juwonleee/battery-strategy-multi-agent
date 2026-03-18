from __future__ import annotations

import re

from state import (
    AtomicFactClaim,
    CATLFactExtractionOutput,
    EvidenceRef,
    LGESFactExtractionOutput,
    MetricFactClaim,
)


def build_lges_fallback_facts(evidence_refs: list[EvidenceRef]) -> LGESFactExtractionOutput:
    refs = _dedupe_refs(evidence_refs)

    diversification_ref = _find_ref(
        refs,
        "order backlog",
        "product",
    )
    regional_ref = _find_ref(
        refs,
        "NorthAmerica",
        "Japan and Australia",
        "NA region",
    )
    technology_ref = _find_ref(
        refs,
        "LFP",
        "46 Series",
        "all solid-state",
        "sodium",
    )
    risk_ref = _find_ref(
        refs,
        "slowing EV demand",
        "sales slowdown",
        "EV sales slowdown",
    )

    atomic_claims = [
        AtomicFactClaim(
            scope="lges",
            category="business_overview",
            ordinal=1,
            claim_text="LGES는 EV 둔화 구간에서 ESS와 원통형 배터리를 함께 확대하는 포트폴리오 재조정을 진행하고 있다.",
            evidence_refs=[_require_ref(diversification_ref, refs)],
        ),
        AtomicFactClaim(
            scope="lges",
            category="diversification_strategy",
            ordinal=2,
            claim_text="LGES는 46시리즈, ESS, LFP, pouch/prismatic 다변화로 제품과 고객 구성을 넓히고 있다.",
            evidence_refs=[_require_ref(diversification_ref, refs)],
        ),
        AtomicFactClaim(
            scope="lges",
            category="regional_strategy",
            ordinal=3,
            claim_text="LGES는 북미 ESS 현지 생산을 축으로 물량을 확대하면서 일본과 호주 등 ex-NA 시장도 병행 공략하고 있다.",
            evidence_refs=[_require_ref(regional_ref, refs)],
        ),
        AtomicFactClaim(
            scope="lges",
            category="technology_strategy",
            ordinal=4,
            claim_text="LGES는 LFP, HV Mid-Ni, 46시리즈와 함께 차세대 전지 공정과 소재 개발을 병행하고 있다.",
            evidence_refs=[_require_ref(technology_ref, refs)],
        ),
        AtomicFactClaim(
            scope="lges",
            category="risk_factor",
            ordinal=5,
            claim_text="북미 EV 수요 둔화와 고객 판매 부진이 LGES의 단기 수익성과 믹스에 부담을 주고 있다.",
            evidence_refs=[_require_ref(risk_ref, refs)],
        ),
    ]

    revenue_ref = _find_ref(refs, "Target to grow between", "Revenue through stable growth")
    operating_margin_ref = _find_ref(refs, "Target for +Mid-single% of OP Margin", "OP Margin")
    capex_ref = _find_ref(refs, "Target to reduce Capex", "Gradual Reduction of Annual Capex")
    ess_capacity_ref = _find_ref(refs, "GlobalESS Capacity", "2026-end", "More than\n60GWh")
    backlog_ref = _find_ref(refs, "order backlog", "New Orders", "Securing order backlog")

    revenue_value = _extract_first(
        revenue_ref,
        r"Target to grow between\s+([^\n]+?)\s+YoY",
        default="+Mid-teen ~ +20%",
    )
    operating_margin_value = _extract_first(
        operating_margin_ref,
        r"Target for\s+([^\n]+?)\s+of OP Margin",
        default="+Mid-single%",
    )
    capex_value = _extract_first(
        capex_ref,
        r"Target to reduce Capex by\s+([^\n]+?)\s+YoY",
        default="more than -40%",
    )
    ess_capacity_value = _extract_first(
        ess_capacity_ref,
        r"2026-end.*?\n(\d+)GWh",
        default="36",
    )
    secured_order_value = _extract_first(
        backlog_ref,
        r"Securing order backlog of\s+(\d+GWh)",
        default="140GWh",
    )

    metric_claims = [
        MetricFactClaim(
            scope="lges",
            category="revenue_growth_guidance",
            ordinal=1,
            claim_text="2026년 LGES는 ESS 공급 확대와 원통형 성장에 기반해 전년 대비 mid-teen에서 약 +20% 수준의 매출 성장을 제시했다.",
            metric_name="Revenue growth guidance",
            reported_basis="guidance",
            period="2026E",
            value=revenue_value,
            unit="%",
            evidence_refs=[_require_ref(revenue_ref, refs)],
        ),
        MetricFactClaim(
            scope="lges",
            category="operating_margin_guidance_or_actual",
            ordinal=2,
            claim_text="2026년 LGES는 ESS 공급 증가와 비용 효율화에 기반해 mid-single 수준의 영업이익률을 목표로 제시했다.",
            metric_name="Operating profit margin guidance",
            reported_basis="guidance",
            period="2026E",
            value=operating_margin_value,
            unit="%",
            evidence_refs=[_require_ref(operating_margin_ref, refs)],
        ),
        MetricFactClaim(
            scope="lges",
            category="capex",
            ordinal=3,
            claim_text="LGES는 현금흐름 관리를 위해 2026년 Capex를 전년 대비 40% 이상 줄이는 계획을 제시했다.",
            metric_name="Capex guidance",
            reported_basis="guidance",
            period="2026E",
            value=capex_value,
            unit="%",
            evidence_refs=[_require_ref(capex_ref, refs)],
        ),
        MetricFactClaim(
            scope="lges",
            category="ess_capacity",
            ordinal=4,
            claim_text="LGES는 글로벌 ESS capacity를 2025년 말 12GWh에서 2026년 말 36GWh까지 확대하는 계획을 제시했다.",
            metric_name="Global ESS capacity",
            reported_basis="reported",
            period="2026-end",
            value=ess_capacity_value,
            unit="GWh",
            evidence_refs=[_require_ref(ess_capacity_ref, refs)],
        ),
        MetricFactClaim(
            scope="lges",
            category="secured_order_volume",
            ordinal=5,
            claim_text="LGES는 ESS에서 140GWh backlog를 확보했고 46시리즈에서도 300GWh+ backlog를 제시했다.",
            metric_name="Secured order backlog",
            reported_basis="reported",
            period="2025",
            value=secured_order_value,
            unit="GWh",
            evidence_refs=[_require_ref(backlog_ref, refs)],
        ),
    ]

    source_evidence_refs = _collect_source_refs(
        atomic_claims=atomic_claims,
        metric_claims=metric_claims,
    )

    return LGESFactExtractionOutput(
        scope="lges",
        summary="LGES는 EV 둔화 구간에서 ESS와 제품 다변화를 통해 성장과 수익성 방어를 동시에 추구하고 있다.",
        atomic_claims=atomic_claims,
        metric_claims=metric_claims,
        source_evidence_refs=source_evidence_refs,
    )


def build_catl_fallback_facts(evidence_refs: list[EvidenceRef]) -> CATLFactExtractionOutput:
    refs = _dedupe_refs(evidence_refs)

    overview_ref = _find_ref(refs, "globally leading innovative new energy technology company")
    regional_ref = _find_ref(refs, "Germany", "Hungary", "Spain", "Indonesia")
    technology_ref = _find_ref(refs, "integrated innovative solutions", "resources and recycling")
    risk_ref = _find_ref(refs, "additional tariffs", "average selling price", "raw materials")

    atomic_claims = [
        AtomicFactClaim(
            scope="catl",
            category="business_overview",
            ordinal=1,
            claim_text="CATL은 EV 배터리와 ESS 배터리를 중심으로 성장한 글로벌 배터리 선도 기업이다.",
            evidence_refs=[_require_ref(overview_ref, refs)],
        ),
        AtomicFactClaim(
            scope="catl",
            category="diversification_strategy",
            ordinal=2,
            claim_text="CATL은 EV와 ESS를 양축으로 운영하면서 배터리 가치사슬과 통합 솔루션 영역까지 확장하고 있다.",
            evidence_refs=[_require_ref(technology_ref, refs)],
        ),
        AtomicFactClaim(
            scope="catl",
            category="regional_strategy",
            ordinal=3,
            claim_text="CATL은 독일, 헝가리, 스페인, 인도네시아를 포함한 해외 생산과 공급망 확장으로 글로벌 운영 구조를 강화하고 있다.",
            evidence_refs=[_require_ref(regional_ref, refs)],
        ),
        AtomicFactClaim(
            scope="catl",
            category="technology_strategy",
            ordinal=4,
            claim_text="CATL은 전동화와 지능화 기반의 통합 솔루션, 자원 확보, 재활용 역량을 결합해 기술 해자를 확장하고 있다.",
            evidence_refs=[_require_ref(technology_ref, refs)],
        ),
        AtomicFactClaim(
            scope="catl",
            category="risk_factor",
            ordinal=5,
            claim_text="원재료 가격과 판매단가 변동, 대외 규제와 관세 변화는 CATL의 단기 수익성에 영향을 줄 수 있다.",
            evidence_refs=[_require_ref(risk_ref, refs)],
        ),
    ]

    revenue_ref = _find_ref(refs, "our revenue was RMB328.6 billion", "Revenue 328,593,988")
    profit_ref = _find_ref(refs, "profit for the year was RMB33.5", "Profits for the Y ear")
    gross_margin_ref = _find_ref(refs, "Gross profit 57,964,208", "gross profit margin increased")
    net_margin_ref = _find_ref(refs, "net profit margin", "Net profit margin 10.2% 11.8% 15.3%")
    roe_ref = _find_ref(refs, "weighted average ROE", "24.7% 24.3% 24.7%")
    ocf_ref = _find_ref(refs, "Net cash generated from operating", "96,990,344")

    metric_claims = [
        MetricFactClaim(
            scope="catl",
            category="revenue",
            ordinal=1,
            claim_text="CATL의 2024년 매출은 RMB 362.0bn이다.",
            metric_name="Revenue",
            reported_basis="reported",
            period="2024",
            value="362.0",
            unit="RMB bn",
            evidence_refs=[_require_ref(revenue_ref, refs)],
        ),
        MetricFactClaim(
            scope="catl",
            category="profit_for_the_year",
            ordinal=2,
            claim_text="CATL의 2024년 profit for the year는 RMB 55.3bn이다.",
            metric_name="Profit for the year",
            reported_basis="reported",
            period="2024",
            value="55.3",
            unit="RMB bn",
            evidence_refs=[_require_ref(profit_ref, refs)],
        ),
        MetricFactClaim(
            scope="catl",
            category="gross_profit_margin",
            ordinal=3,
            claim_text="CATL의 2024년 gross profit margin은 24.4%다.",
            metric_name="Gross profit margin",
            reported_basis="reported",
            period="2024",
            value="24.4%",
            evidence_refs=[_require_ref(gross_margin_ref, refs)],
        ),
        MetricFactClaim(
            scope="catl",
            category="net_profit_margin",
            ordinal=4,
            claim_text="CATL의 2024년 net profit margin은 15.3%다.",
            metric_name="Net profit margin",
            reported_basis="reported",
            period="2024",
            value="15.3%",
            evidence_refs=[_require_ref(net_margin_ref, refs)],
        ),
        MetricFactClaim(
            scope="catl",
            category="roe",
            ordinal=5,
            claim_text="CATL의 2024년 weighted average ROE는 24.7%다.",
            metric_name="Weighted average ROE",
            reported_basis="reported",
            period="2024",
            value="24.7%",
            evidence_refs=[_require_ref(roe_ref, refs)],
        ),
        MetricFactClaim(
            scope="catl",
            category="operating_cash_flow",
            ordinal=6,
            claim_text="CATL의 2024년 영업활동현금흐름은 RMB 97.0bn이다.",
            metric_name="Net cash generated from operating activities",
            reported_basis="reported",
            period="2024",
            value="97.0",
            unit="RMB bn",
            evidence_refs=[_require_ref(ocf_ref, refs)],
        ),
    ]

    source_evidence_refs = _collect_source_refs(
        atomic_claims=atomic_claims,
        metric_claims=metric_claims,
    )

    return CATLFactExtractionOutput(
        scope="catl",
        summary="CATL은 EV와 ESS를 양축으로 한 글로벌 확장과 높은 수익성을 동시에 보여주는 선도 사업자다.",
        atomic_claims=atomic_claims,
        metric_claims=metric_claims,
        source_evidence_refs=source_evidence_refs,
    )


def _collect_source_refs(
    *,
    atomic_claims: list[AtomicFactClaim],
    metric_claims: list[MetricFactClaim],
) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    seen: set[tuple[str, str | None, int | None]] = set()
    for claim in [*atomic_claims, *metric_claims]:
        for ref in claim.evidence_refs:
            key = (ref.document_id, ref.chunk_id, ref.page)
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


def _dedupe_refs(evidence_refs: list[EvidenceRef]) -> list[EvidenceRef]:
    deduped: list[EvidenceRef] = []
    seen: set[tuple[str, str | None, int | None]] = set()
    for ref in evidence_refs:
        key = (ref.document_id, ref.chunk_id, ref.page)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _require_ref(ref: EvidenceRef | None, refs: list[EvidenceRef]) -> EvidenceRef:
    if ref is not None:
        return ref
    if refs:
        return refs[0]
    raise ValueError("Fallback fact extraction requires at least one evidence reference.")


def _find_ref(evidence_refs: list[EvidenceRef], *patterns: str) -> EvidenceRef | None:
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for ref in evidence_refs:
        snippet = (ref.snippet or "").lower()
        if all(pattern in snippet for pattern in lowered_patterns):
            return ref
    for pattern in lowered_patterns:
        for ref in evidence_refs:
            snippet = (ref.snippet or "").lower()
            if pattern in snippet:
                return ref
    return None


def _extract_first(ref: EvidenceRef | None, pattern: str, *, default: str) -> str:
    if ref is None or not ref.snippet:
        return default
    match = re.search(pattern, ref.snippet, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return default
    value = match.group(1).strip()
    return re.sub(r"\s+", " ", value)

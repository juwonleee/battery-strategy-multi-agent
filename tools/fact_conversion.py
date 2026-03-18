from state import (
    CompanyProfile,
    FactExtractionOutput,
    FinancialIndicator,
    MarketContext,
    MarketFactExtractionOutput,
)


def build_market_context_from_facts(
    extraction: MarketFactExtractionOutput,
) -> MarketContext:
    comparison_axes = [
        claim.claim_text
        for claim in extraction.atomic_claims
        if claim.category == "comparison_axis"
    ][:5]
    key_findings = [
        claim.claim_text
        for claim in extraction.atomic_claims
        if claim.category != "comparison_axis"
    ][:5]
    summary = extraction.summary or _first_non_empty(
        key_findings,
        default="정보 부족",
    )
    return MarketContext(
        summary=summary,
        key_findings=key_findings,
        comparison_axes=comparison_axes,
        evidence_refs=extraction.source_evidence_refs,
    )


def build_company_profile_from_facts(
    extraction: FactExtractionOutput,
    *,
    company_name: str,
) -> CompanyProfile:
    return CompanyProfile(
        company_name=company_name,
        business_overview=_first_non_empty(
            _texts_for_category(extraction, "business_overview"),
            default=extraction.summary or "정보 부족",
        ),
        core_products=_texts_for_category(extraction, "core_product"),
        diversification_strategy=_texts_for_category(extraction, "diversification_strategy"),
        regional_strategy=_texts_for_category(extraction, "regional_strategy"),
        technology_strategy=_texts_for_category(extraction, "technology_strategy"),
        financial_indicators=[
            FinancialIndicator(
                metric=_metric_label(metric_claim),
                value=_metric_value(metric_claim),
            )
            for metric_claim in extraction.metric_claims
        ],
        risk_factors=_texts_for_category(extraction, "risk_factor"),
        evidence_refs=extraction.source_evidence_refs,
    )


def _texts_for_category(extraction: FactExtractionOutput, category: str) -> list[str]:
    return [
        claim.claim_text
        for claim in extraction.atomic_claims
        if claim.category == category
    ]


def _metric_label(metric_claim) -> str:
    return metric_claim.metric_name or metric_claim.normalized_metric_name or metric_claim.category


def _metric_value(metric_claim) -> str:
    value = str(metric_claim.value)
    if metric_claim.unit:
        value = f"{value} {metric_claim.unit}"
    if metric_claim.period:
        return f"{metric_claim.period}: {value}"
    return value


def _first_non_empty(values: list[str], *, default: str) -> str:
    for value in values:
        if value.strip():
            return value
    return default

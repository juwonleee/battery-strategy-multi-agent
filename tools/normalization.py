from __future__ import annotations

import re

from state import (
    CATLFactExtractionOutput,
    LGESFactExtractionOutput,
    MetricComparisonRow,
    MetricFactClaim,
    NormalizedMetric,
    normalize_claim_category,
)


class MetricNormalizationError(ValueError):
    """Raised when raw metric claims cannot be normalized safely."""


CATL_NET_MARGIN_TOLERANCE = 0.5
PERIOD_UNSPECIFIED = "period_unspecified"

_NORMALIZED_NAME_BY_CATEGORY = {
    "revenue_growth_guidance": "revenue_growth",
    "operating_margin_guidance_or_actual": "operating_margin",
    "capex": "capex",
    "ess_capacity": "ess_capacity",
    "secured_order_volume": "secured_order_volume",
    "revenue": "revenue",
    "profit_for_the_year": "profit_for_the_year",
    "gross_profit_margin": "gross_profit_margin",
    "net_profit_margin": "net_profit_margin",
    "roe": "roe",
    "operating_cash_flow": "operating_cash_flow",
}

_DEFAULT_REPORTED_BASIS = {
    "revenue_growth_guidance": "guidance",
    "operating_margin_guidance_or_actual": "guidance_or_actual",
    "capex": "reported",
    "ess_capacity": "reported",
    "secured_order_volume": "reported",
    "revenue": "reported",
    "profit_for_the_year": "reported",
    "gross_profit_margin": "reported",
    "net_profit_margin": "reported",
    "roe": "reported",
    "operating_cash_flow": "reported",
}


def normalize_lges_metrics(extraction: LGESFactExtractionOutput) -> list[NormalizedMetric]:
    return _normalize_company_metrics(extraction.scope, extraction.metric_claims)


def normalize_catl_metrics(extraction: CATLFactExtractionOutput) -> list[NormalizedMetric]:
    normalized_metrics = _normalize_company_metrics(extraction.scope, extraction.metric_claims)
    return _apply_catl_net_profit_margin_rules(normalized_metrics)


def build_profitability_reported_rows(
    lges_metrics: list[NormalizedMetric],
    catl_metrics: list[NormalizedMetric],
) -> list[MetricComparisonRow]:
    rows: list[MetricComparisonRow] = []

    lges_metric = _select_primary_metric(lges_metrics, "operating_margin")
    if lges_metric is not None:
        rows.append(
            MetricComparisonRow(
                row_id="profitability_reported-lges-operating_margin",
                row_group="profitability_reported",
                metric_name="operating_margin",
                period=lges_metric.period,
                lges_value=_format_metric_value(lges_metric),
                catl_value=None,
                basis_note=f"LGES {lges_metric.reported_basis}",
                evidence_refs=lges_metric.evidence_refs,
            )
        )

    catl_metric = _select_primary_metric(catl_metrics, "net_profit_margin")
    if catl_metric is not None:
        rows.append(
            MetricComparisonRow(
                row_id="profitability_reported-catl-net_profit_margin",
                row_group="profitability_reported",
                metric_name="net_profit_margin",
                period=catl_metric.period,
                lges_value=None,
                catl_value=_format_metric_value(catl_metric),
                basis_note=f"CATL {catl_metric.reported_basis}",
                evidence_refs=catl_metric.evidence_refs,
            )
        )

    return rows


def _normalize_company_metrics(
    scope: str,
    metric_claims: list[MetricFactClaim],
) -> list[NormalizedMetric]:
    normalized_metrics = [
        _normalize_metric_claim(scope, claim)
        for claim in metric_claims
    ]
    return sorted(
        normalized_metrics,
        key=lambda item: (
            item.normalized_metric_name,
            item.period,
            item.source_claim_ids[0],
        ),
    )


def _normalize_metric_claim(scope: str, claim: MetricFactClaim) -> NormalizedMetric:
    numeric_value, inferred_unit = _extract_numeric_value(claim)
    return NormalizedMetric(
        scope=scope,
        normalized_metric_name=_NORMALIZED_NAME_BY_CATEGORY.get(claim.category, claim.category),
        reported_basis=_normalize_reported_basis(claim),
        period=_normalize_period(claim.period),
        value=numeric_value if numeric_value is not None else str(claim.value),
        numeric_value=numeric_value,
        unit=claim.unit or inferred_unit,
        source_claim_ids=[claim.claim_id],
        evidence_refs=claim.evidence_refs,
    )


def _apply_catl_net_profit_margin_rules(
    normalized_metrics: list[NormalizedMetric],
) -> list[NormalizedMetric]:
    metrics_by_name = _group_by_metric_name(normalized_metrics)
    direct_margins = metrics_by_name.get("net_profit_margin", [])
    revenues = _index_metrics_by_period(metrics_by_name.get("revenue", []))
    profits = _index_metrics_by_period(metrics_by_name.get("profit_for_the_year", []))

    derived_margins: list[NormalizedMetric] = []

    if direct_margins:
        for direct_margin in direct_margins:
            revenue_metric = revenues.get(direct_margin.period)
            profit_metric = profits.get(direct_margin.period)
            if revenue_metric and profit_metric:
                _validate_direct_margin_against_calculation(
                    direct_margin,
                    revenue_metric,
                    profit_metric,
                )
        return normalized_metrics

    if not revenues or not profits:
        return normalized_metrics

    aligned_periods = sorted(set(revenues) & set(profits))
    if not aligned_periods:
        raise MetricNormalizationError(
            "Cannot derive CATL net_profit_margin because profit_for_the_year and "
            "revenue periods do not align."
        )

    for period in aligned_periods:
        revenue_metric = revenues[period]
        profit_metric = profits[period]
        derived_value = _calculate_margin_percent(profit_metric, revenue_metric)
        derived_margins.append(
            NormalizedMetric(
                scope="catl",
                normalized_metric_name="net_profit_margin",
                reported_basis="derived_from_profit_for_the_year_and_revenue",
                period=period,
                value=derived_value,
                numeric_value=derived_value,
                unit="percent",
                source_claim_ids=[
                    *profit_metric.source_claim_ids,
                    *revenue_metric.source_claim_ids,
                ],
                evidence_refs=_merge_evidence_refs(
                    profit_metric.evidence_refs,
                    revenue_metric.evidence_refs,
                ),
                is_derived=True,
                derivation_note="profit_for_the_year / revenue * 100",
            )
        )

    return sorted(
        [*normalized_metrics, *derived_margins],
        key=lambda item: (
            item.normalized_metric_name,
            item.period,
            item.source_claim_ids[0],
        ),
    )


def _validate_direct_margin_against_calculation(
    direct_margin: NormalizedMetric,
    revenue_metric: NormalizedMetric,
    profit_metric: NormalizedMetric,
) -> None:
    if direct_margin.numeric_value is None:
        return

    calculated_margin = _calculate_margin_percent(profit_metric, revenue_metric)
    if abs(direct_margin.numeric_value - calculated_margin) > CATL_NET_MARGIN_TOLERANCE:
        raise MetricNormalizationError(
            "CATL net_profit_margin direct value does not match the "
            "profit_for_the_year / revenue calculation within tolerance."
        )


def _calculate_margin_percent(
    numerator_metric: NormalizedMetric,
    denominator_metric: NormalizedMetric,
) -> float:
    if numerator_metric.period != denominator_metric.period:
        raise MetricNormalizationError(
            "Cannot calculate CATL net_profit_margin because periods are not aligned."
        )
    if numerator_metric.numeric_value is None or denominator_metric.numeric_value is None:
        raise MetricNormalizationError(
            "Cannot calculate CATL net_profit_margin because revenue or "
            "profit_for_the_year is non-numeric."
        )
    if denominator_metric.numeric_value == 0:
        raise MetricNormalizationError(
            "Cannot calculate CATL net_profit_margin because revenue is zero."
        )
    return round((numerator_metric.numeric_value / denominator_metric.numeric_value) * 100, 4)


def _group_by_metric_name(
    metrics: list[NormalizedMetric],
) -> dict[str, list[NormalizedMetric]]:
    grouped: dict[str, list[NormalizedMetric]] = {}
    for metric in metrics:
        grouped.setdefault(metric.normalized_metric_name, []).append(metric)
    return grouped


def _index_metrics_by_period(
    metrics: list[NormalizedMetric],
) -> dict[str, NormalizedMetric]:
    indexed: dict[str, NormalizedMetric] = {}
    for metric in metrics:
        if metric.period == PERIOD_UNSPECIFIED:
            continue
        indexed.setdefault(metric.period, metric)
    return indexed


def _select_primary_metric(
    metrics: list[NormalizedMetric],
    normalized_metric_name: str,
) -> NormalizedMetric | None:
    filtered = [
        metric
        for metric in metrics
        if metric.normalized_metric_name == normalized_metric_name
    ]
    if not filtered:
        return None
    return sorted(
        filtered,
        key=lambda item: (item.period, item.source_claim_ids[0]),
    )[-1]


def _format_metric_value(metric: NormalizedMetric) -> str:
    if isinstance(metric.value, str):
        return metric.value
    if metric.unit in {"percent", "%"}:
        return f"{metric.value:g}%"
    if metric.unit:
        return f"{metric.value:g} {metric.unit}"
    return f"{metric.value:g}"


def _normalize_reported_basis(claim: MetricFactClaim) -> str:
    if claim.reported_basis:
        return normalize_claim_category(claim.reported_basis)
    return _DEFAULT_REPORTED_BASIS.get(claim.category, "reported")


def _normalize_period(period: str | None) -> str:
    if period is None or not period.strip():
        return PERIOD_UNSPECIFIED
    return period.strip()


def _extract_numeric_value(claim: MetricFactClaim) -> tuple[float | None, str | None]:
    if isinstance(claim.value, (int, float)):
        return float(claim.value), claim.unit

    raw_value = str(claim.value).strip()
    compact = raw_value.replace(",", "")
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(%)?", compact)
    if match:
        numeric_value = float(match.group(1))
        inferred_unit = "percent" if match.group(2) else claim.unit
        return numeric_value, inferred_unit
    return None, claim.unit


def _merge_evidence_refs(*evidence_lists):
    merged = []
    seen = set()
    for evidence_list in evidence_lists:
        for ref in evidence_list:
            key = (ref.document_id, ref.chunk_id, ref.page)
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
    return merged

import pytest

from state import CATLFactExtractionOutput, EvidenceRef, LGESFactExtractionOutput, MetricFactClaim
from tools.normalization import (
    MetricNormalizationError,
    build_profitability_reported_rows,
    normalize_catl_metrics,
    normalize_lges_metrics,
)


def test_normalize_catl_metrics_prefers_direct_net_profit_margin():
    catl_output = _build_catl_output(net_profit_margin_value="10%")

    normalized_metrics = normalize_catl_metrics(catl_output)
    net_profit_metrics = [
        metric
        for metric in normalized_metrics
        if metric.normalized_metric_name == "net_profit_margin"
    ]

    assert len(net_profit_metrics) == 1
    assert net_profit_metrics[0].is_derived is False
    assert net_profit_metrics[0].numeric_value == 10.0


def test_normalize_catl_metrics_falls_back_to_profit_for_the_year_divided_by_revenue():
    catl_output = _build_catl_output(net_profit_margin_value=None)

    normalized_metrics = normalize_catl_metrics(catl_output)
    net_profit_metrics = [
        metric
        for metric in normalized_metrics
        if metric.normalized_metric_name == "net_profit_margin"
    ]

    assert len(net_profit_metrics) == 1
    assert net_profit_metrics[0].is_derived is True
    assert net_profit_metrics[0].numeric_value == 10.0
    assert net_profit_metrics[0].reported_basis == "derived_from_profit_for_the_year_and_revenue"


def test_normalize_catl_metrics_fails_when_direct_margin_mismatches_calculation():
    catl_output = _build_catl_output(net_profit_margin_value="13%")

    with pytest.raises(
        MetricNormalizationError,
        match="direct value does not match",
    ):
        normalize_catl_metrics(catl_output)


def test_profitability_reported_rows_do_not_merge_lges_and_catl_profitability():
    lges_output = _build_lges_output()
    catl_output = _build_catl_output(net_profit_margin_value=None)

    lges_metrics = normalize_lges_metrics(lges_output)
    catl_metrics = normalize_catl_metrics(catl_output)
    rows = build_profitability_reported_rows(lges_metrics, catl_metrics)

    assert len(rows) == 2
    assert {row.metric_name for row in rows} == {
        "operating_margin",
        "net_profit_margin",
    }
    assert all(row.row_group == "profitability_reported" for row in rows)
    assert all(not (row.lges_value and row.catl_value) for row in rows)


def _build_lges_output() -> LGESFactExtractionOutput:
    ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)
    return LGESFactExtractionOutput(
        scope="lges",
        atomic_claims=[],
        metric_claims=[
            _metric_claim(
                scope="lges",
                category="revenue_growth_guidance",
                ordinal=1,
                metric_name="Revenue growth guidance",
                value="mid-teen",
                period="FY2025",
                evidence_ref=ref,
            ),
            _metric_claim(
                scope="lges",
                category="operating_margin_guidance_or_actual",
                ordinal=2,
                metric_name="Operating margin",
                value="7.2%",
                period="FY2025",
                evidence_ref=ref,
            ),
            _metric_claim(
                scope="lges",
                category="capex",
                ordinal=3,
                metric_name="Capex",
                value=10.0,
                period="FY2025",
                unit="KRW tn",
                evidence_ref=ref,
            ),
            _metric_claim(
                scope="lges",
                category="ess_capacity",
                ordinal=4,
                metric_name="ESS capacity",
                value=15.0,
                period="FY2025",
                unit="GWh",
                evidence_ref=ref,
            ),
            _metric_claim(
                scope="lges",
                category="secured_order_volume",
                ordinal=5,
                metric_name="Secured order volume",
                value=100.0,
                period="FY2025",
                unit="GWh",
                evidence_ref=ref,
            ),
        ],
        source_evidence_refs=[ref],
    )


def _build_catl_output(net_profit_margin_value: str | None) -> CATLFactExtractionOutput:
    ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p008-c01", page=8)
    metric_claims = [
        _metric_claim(
            scope="catl",
            category="revenue",
            ordinal=1,
            metric_name="Revenue",
            value=200.0,
            period="FY2024",
            unit="CNY bn",
            evidence_ref=ref,
        ),
        _metric_claim(
            scope="catl",
            category="profit_for_the_year",
            ordinal=2,
            metric_name="Profit for the year",
            value=20.0,
            period="FY2024",
            unit="CNY bn",
            evidence_ref=ref,
        ),
        _metric_claim(
            scope="catl",
            category="gross_profit_margin",
            ordinal=3,
            metric_name="Gross profit margin",
            value="23%",
            period="FY2024",
            evidence_ref=ref,
        ),
        _metric_claim(
            scope="catl",
            category="roe",
            ordinal=4,
            metric_name="ROE",
            value="19%",
            period="FY2024",
            evidence_ref=ref,
        ),
        _metric_claim(
            scope="catl",
            category="operating_cash_flow",
            ordinal=5,
            metric_name="Operating cash flow",
            value=80.0,
            period="FY2024",
            unit="CNY bn",
            evidence_ref=ref,
        ),
    ]
    if net_profit_margin_value is not None:
        metric_claims.append(
            _metric_claim(
                scope="catl",
                category="net_profit_margin",
                ordinal=6,
                metric_name="Net profit margin",
                value=net_profit_margin_value,
                period="FY2024",
                evidence_ref=ref,
            )
        )

    return CATLFactExtractionOutput(
        scope="catl",
        atomic_claims=[],
        metric_claims=metric_claims,
        source_evidence_refs=[ref],
    )


def _metric_claim(
    *,
    scope: str,
    category: str,
    ordinal: int,
    metric_name: str,
    value,
    period: str,
    evidence_ref: EvidenceRef,
    unit: str | None = None,
) -> MetricFactClaim:
    return MetricFactClaim(
        scope=scope,
        category=category,
        ordinal=ordinal,
        claim_text=f"{metric_name}: {value}",
        metric_name=metric_name,
        value=value,
        period=period,
        unit=unit,
        evidence_refs=[evidence_ref],
    )

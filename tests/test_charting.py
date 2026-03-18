from state import EvidenceRef, MetricComparisonRow, NormalizedMetric
from tools.charting import build_chart_specs


def test_build_chart_specs_returns_required_fixed_chart_ids():
    charts = build_chart_specs(
        lges_metrics=[],
        catl_metrics=[
            NormalizedMetric(
                scope="catl",
                normalized_metric_name="revenue",
                reported_basis="reported",
                period="FY2024",
                value=200.0,
                numeric_value=200.0,
                unit="CNY bn",
                source_claim_ids=["catl-revenue-1"],
                evidence_refs=[EvidenceRef(document_id="catl-001", chunk_id="catl-001-p008-c01", page=8)],
            )
        ],
        metric_comparison_rows=_profitability_rows(),
    )

    assert [chart.chart_id for chart in charts] == ["revenue_comparison"]
    assert charts[0].series[0].label == "LGES Revenue"
    assert charts[0].series[0].values == [None]
    assert charts[0].series[1].values == [200.0]
    assert charts[0].title == "Revenue Comparison"


def test_build_chart_specs_maps_profitability_rows_to_expected_series_only():
    extra_ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)
    charts = build_chart_specs(
        lges_metrics=[],
        catl_metrics=[],
        metric_comparison_rows=[
            *_profitability_rows(),
            MetricComparisonRow(
                row_id="profitability_extra",
                row_group="profitability_reported",
                metric_name="gross_profit_margin",
                period="FY2024",
                lges_value=None,
                catl_value="22%",
                basis_note="Extra row that should not feed chart 2.",
                evidence_refs=[extra_ref],
            ),
        ],
    )

    assert charts == []


def _profitability_rows() -> list[MetricComparisonRow]:
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)
    catl_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p008-c01", page=8)
    return [
        MetricComparisonRow(
            row_id="profitability_lges",
            row_group="profitability_reported",
            metric_name="operating_margin",
            period="FY2025",
            lges_value="7.2%",
            catl_value=None,
            basis_note="LGES reported basis",
            evidence_refs=[lges_ref],
        ),
        MetricComparisonRow(
            row_id="profitability_catl",
            row_group="profitability_reported",
            metric_name="net_profit_margin",
            period="FY2024",
            lges_value=None,
            catl_value="11%",
            basis_note="CATL reported basis",
            evidence_refs=[catl_ref],
        ),
    ]

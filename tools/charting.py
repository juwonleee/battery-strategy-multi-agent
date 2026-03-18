from __future__ import annotations

import re

from state import ChartSeries, ChartSpec, MetricComparisonRow, NormalizedMetric


REQUIRED_CHART_IDS = (
    "revenue_trend",
    "profitability_reported",
)

_NUMERIC_PATTERN = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def build_chart_specs(
    *,
    lges_metrics: list[NormalizedMetric],
    catl_metrics: list[NormalizedMetric],
    metric_comparison_rows: list[MetricComparisonRow],
) -> list[ChartSpec]:
    charts: list[ChartSpec] = []

    revenue_chart = _build_revenue_trend_chart(
        lges_metrics=lges_metrics,
        catl_metrics=catl_metrics,
    )
    if revenue_chart is not None:
        charts.append(revenue_chart)

    profitability_chart = _build_profitability_reported_chart(metric_comparison_rows)
    if profitability_chart is not None:
        charts.append(profitability_chart)

    return charts


def missing_required_chart_ids(charts: list[ChartSpec]) -> list[str]:
    actual = {chart.chart_id for chart in charts}
    return [chart_id for chart_id in REQUIRED_CHART_IDS if chart_id not in actual]


def _build_revenue_trend_chart(
    *,
    lges_metrics: list[NormalizedMetric],
    catl_metrics: list[NormalizedMetric],
) -> ChartSpec | None:
    lges_revenue = _index_numeric_metrics(lges_metrics, "revenue")
    catl_revenue = _index_numeric_metrics(catl_metrics, "revenue")
    periods = sorted(set(lges_revenue) | set(catl_revenue))
    if not periods:
        return None

    return ChartSpec(
        chart_id="revenue_trend",
        title="Revenue Trend",
        series=[
            ChartSeries(
                label="LGES Revenue",
                values=[_metric_value_for_period(lges_revenue, period) for period in periods],
                source_row_ids=[
                    claim_id
                    for period in periods
                    for claim_id in _metric_source_ids_for_period(lges_revenue, period)
                ],
            ),
            ChartSeries(
                label="CATL Revenue",
                values=[_metric_value_for_period(catl_revenue, period) for period in periods],
                source_row_ids=[
                    claim_id
                    for period in periods
                    for claim_id in _metric_source_ids_for_period(catl_revenue, period)
                ],
            ),
        ],
        x_axis_periods=periods,
        y_axis_label=_resolve_revenue_axis_label(lges_revenue, catl_revenue),
    )


def _build_profitability_reported_chart(
    metric_comparison_rows: list[MetricComparisonRow],
) -> ChartSpec | None:
    lges_row = _select_profitability_row(
        metric_comparison_rows,
        metric_name="operating_margin",
        owner="lges",
    )
    catl_row = _select_profitability_row(
        metric_comparison_rows,
        metric_name="net_profit_margin",
        owner="catl",
    )
    if lges_row is None or catl_row is None:
        return None

    periods = [period for period in [lges_row.period, catl_row.period] if period]
    if not periods:
        periods = ["period_unspecified"]
    ordered_periods = list(dict.fromkeys(periods))

    return ChartSpec(
        chart_id="profitability_reported",
        title="Reported Profitability",
        series=[
            ChartSeries(
                label="LGES Operating Margin",
                values=[
                    _parse_row_value(lges_row.lges_value) if period == (lges_row.period or "period_unspecified") else None
                    for period in ordered_periods
                ],
                source_row_ids=[lges_row.row_id],
            ),
            ChartSeries(
                label="CATL Net Profit Margin",
                values=[
                    _parse_row_value(catl_row.catl_value) if period == (catl_row.period or "period_unspecified") else None
                    for period in ordered_periods
                ],
                source_row_ids=[catl_row.row_id],
            ),
        ],
        x_axis_periods=ordered_periods,
        y_axis_label="Margin (%)",
    )


def _index_numeric_metrics(
    metrics: list[NormalizedMetric],
    normalized_metric_name: str,
) -> dict[str, NormalizedMetric]:
    indexed: dict[str, NormalizedMetric] = {}
    for metric in metrics:
        if metric.normalized_metric_name != normalized_metric_name:
            continue
        if metric.numeric_value is None:
            continue
        current = indexed.get(metric.period)
        if current is None or tuple(metric.source_claim_ids) < tuple(current.source_claim_ids):
            indexed[metric.period] = metric
    return indexed


def _resolve_revenue_axis_label(
    lges_revenue: dict[str, NormalizedMetric],
    catl_revenue: dict[str, NormalizedMetric],
) -> str:
    units = {
        metric.unit
        for metric in [*lges_revenue.values(), *catl_revenue.values()]
        if metric.unit
    }
    if len(units) == 1:
        return f"Revenue ({next(iter(units))})"
    if units:
        return "Revenue (reported units)"
    return "Revenue"


def _metric_value_for_period(
    metric_index: dict[str, NormalizedMetric],
    period: str,
) -> float | None:
    metric = metric_index.get(period)
    return metric.numeric_value if metric is not None else None


def _metric_source_ids_for_period(
    metric_index: dict[str, NormalizedMetric],
    period: str,
) -> list[str]:
    metric = metric_index.get(period)
    return metric.source_claim_ids if metric is not None else []


def _select_profitability_row(
    rows: list[MetricComparisonRow],
    *,
    metric_name: str,
    owner: str,
) -> MetricComparisonRow | None:
    matched = [
        row
        for row in rows
        if row.row_group == "profitability_reported"
        and row.metric_name == metric_name
        and ((owner == "lges" and row.lges_value) or (owner == "catl" and row.catl_value))
    ]
    if not matched:
        return None
    return sorted(matched, key=lambda row: row.row_id)[0]


def _parse_row_value(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    match = _NUMERIC_PATTERN.search(raw_value)
    if match is None:
        return None
    return float(match.group(0).replace(",", ""))

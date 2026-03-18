from __future__ import annotations

from html import escape
from pathlib import Path

from state import (
    AgentState,
    AtomicFactClaim,
    ChartSpec,
    EvidenceRef,
    MetricFactClaim,
    ReportArtifact,
    ReportSpec,
    ScoreCriterion,
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - handled at runtime
    sync_playwright = None


class ReportExportError(RuntimeError):
    """Raised when a report artifact cannot be exported."""


def build_report_spec(state: AgentState) -> ReportSpec:
    return _build_report_spec(state)


def assemble_markdown_report(state: AgentState) -> str:
    report_spec = build_report_spec(state)
    manifest_map = {item.document_id: item for item in report_spec.references}
    claim_map = _build_claim_map(report_spec)

    sections = [
        f"# {report_spec.title}",
        "",
        "## Summary",
        *_render_summary_markdown(state, report_spec, manifest_map, claim_map),
        "",
        "## 시장 배경",
        *_render_claim_section_markdown(
            _claims_for_scope(report_spec.atomic_claims, "market"),
            manifest_map,
            fallback=[state.get("market_context_summary", "정보 부족")],
        ),
        "",
        "## LGES",
        *_render_company_section_markdown(
            company_name="LG Energy Solution",
            atomic_claims=_claims_for_scope(report_spec.atomic_claims, "lges"),
            metric_claims=_metric_claims_for_scope(report_spec.metric_claims, "lges"),
            manifest_map=manifest_map,
        ),
        "",
        "## CATL",
        *_render_company_section_markdown(
            company_name="CATL",
            atomic_claims=_claims_for_scope(report_spec.atomic_claims, "catl"),
            metric_claims=_metric_claims_for_scope(report_spec.metric_claims, "catl"),
            manifest_map=manifest_map,
        ),
        "",
        "## 정량 비교표",
        *_render_metric_comparison_table_markdown(
            report_spec.metric_comparison_rows,
            manifest_map,
        ),
        "",
        "## 차트",
        *_render_chart_specs_markdown(report_spec.charts),
        "",
        "## SWOT",
        *_render_swot(report_spec.swot_matrix),
        "",
        "## Scorecard",
        *_render_score_criteria_markdown(report_spec.score_criteria, manifest_map),
        "",
        "## 종합 판단",
        _render_final_judgment_markdown(report_spec, manifest_map, claim_map),
        "",
        "## Reference",
        *_render_reference_lines(report_spec, manifest_map, claim_map),
    ]
    return "\n".join(line for line in sections if line is not None).strip() + "\n"


def assemble_html_report(state: AgentState) -> str:
    report_spec = build_report_spec(state)
    manifest_map = {item.document_id: item for item in report_spec.references}
    claim_map = _build_claim_map(report_spec)

    summary_items = _render_summary_markdown(state, report_spec, manifest_map, claim_map)
    sections = [
        f"""
        <header class="hero">
          <div class="eyebrow">Battery Strategy Intelligence</div>
          <div class="hero-heading">
            <h1>{_html(report_spec.title)}</h1>
            <p class="hero-copy">{_html(state['goal'])}</p>
          </div>
        </header>
        """,
        f'<section class="summary-grid">{"".join(_render_summary_card_html(item) for item in summary_items)}</section>',
        _wrap_section(
            "시장 배경",
            _render_claim_section_html(
                _claims_for_scope(report_spec.atomic_claims, "market"),
                manifest_map,
                fallback=[state.get("market_context_summary", "정보 부족")],
            ),
        ),
        _wrap_section(
            "LGES",
            _render_company_section_html(
                "LG Energy Solution",
                _claims_for_scope(report_spec.atomic_claims, "lges"),
                _metric_claims_for_scope(report_spec.metric_claims, "lges"),
                manifest_map,
            ),
        ),
        _wrap_section(
            "CATL",
            _render_company_section_html(
                "CATL",
                _claims_for_scope(report_spec.atomic_claims, "catl"),
                _metric_claims_for_scope(report_spec.metric_claims, "catl"),
                manifest_map,
            ),
        ),
        _wrap_section(
            "정량 비교표",
            _render_metric_comparison_table_html(
                report_spec.metric_comparison_rows,
                manifest_map,
            ),
        ),
        _wrap_section(
            "차트",
            _render_chart_specs_html(report_spec.charts),
        ),
        _wrap_section(
            "SWOT",
            _render_swot_html(report_spec.swot_matrix),
        ),
        _wrap_section(
            "Scorecard",
            _render_score_criteria_html(report_spec.score_criteria, manifest_map),
        ),
        _wrap_section(
            "종합 판단",
            f'<div class="panel"><p>{_html(_render_final_judgment_markdown(report_spec, manifest_map, claim_map))}</p></div>',
        ),
        _wrap_section(
            "Reference",
            _render_reference_html(report_spec, manifest_map, claim_map),
        ),
    ]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html(report_spec.title)}</title>
  <style>
    :root {{
      --ink: #162231;
      --muted: #59677a;
      --line: #cfd8e3;
      --line-strong: #8da0b6;
      --accent: #23466a;
      --paper: #ffffff;
    }}
    @page {{
      size: A4;
      margin: 12mm 12mm 14mm 12mm;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      background: #fff;
      color: var(--ink);
      font-family: "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
      line-height: 1.58;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    body {{ font-size: 13px; }}
    .report {{
      width: 100%;
      max-width: 210mm;
      margin: 0 auto;
      padding: 12mm 12mm 16mm;
      background: var(--paper);
    }}
    .hero {{
      border-bottom: 2px solid var(--accent);
      padding: 0 0 8mm;
      margin-bottom: 7mm;
    }}
    .eyebrow {{
      margin-bottom: 3mm;
      color: var(--muted);
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .hero-heading {{
      display: flex;
      flex-direction: column;
      gap: 2mm;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.25;
      color: var(--accent);
    }}
    .hero-copy {{
      margin: 0;
      color: var(--ink);
      font-size: 13px;
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      color: var(--accent);
    }}
    h3 {{
      margin: 0 0 2.5mm;
      font-size: 14px;
      line-height: 1.35;
      color: var(--ink);
    }}
    p {{ margin: 0; }}
    .summary-grid,
    .chart-grid,
    .scorecard-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 4mm;
    }}
    .swot-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 4mm;
      margin-top: 3mm;
    }}
    .summary-grid {{
      margin-bottom: 7mm;
    }}
    .section {{
      margin-top: 7mm;
    }}
    .section-header {{
      display: flex;
      align-items: flex-end;
      gap: 4mm;
      margin-bottom: 3mm;
    }}
    .section-rule {{
      flex: 1;
      border-bottom: 1px solid var(--line);
      min-width: 20mm;
    }}
    .card,
    .panel,
    .scorecard,
    .chart-card,
    .swot-card {{
      background: #fff;
      border: 1px solid var(--line);
      padding: 4mm;
    }}
    .card {{
      border-left: 4px solid var(--accent);
    }}
    .card strong {{
      display: block;
      margin-bottom: 1.5mm;
      color: var(--accent);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .comparison-panel {{
      border: 1px solid var(--line);
      padding: 0;
    }}
    .comparison-table,
    .chart-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    .comparison-table th,
    .comparison-table td,
    .chart-table th,
    .chart-table td {{
      border: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .comparison-table th,
    .chart-table th {{
      color: var(--accent);
      font-weight: 700;
    }}
    .chart-card h3 {{
      margin-bottom: 1.5mm;
    }}
    .chart-meta {{
      margin: 0 0 2.5mm;
      color: var(--muted);
      font-size: 12px;
    }}
    .chart-series-label {{
      font-weight: 700;
      white-space: nowrap;
    }}
    .bullet-list,
    .reference-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .bullet-list li,
    .reference-list li {{
      margin-bottom: 6px;
    }}
    .citation {{
      color: var(--muted);
      font-size: 12px;
    }}
    .empty {{
      color: var(--muted);
      font-style: italic;
    }}
    .section,
    .chart-card,
    .scorecard,
    .swot-card,
    .card {{
      break-inside: avoid;
      page-break-inside: avoid;
    }}
    .comparison-panel,
    .reference-panel {{
      break-inside: auto;
      page-break-inside: auto;
    }}
    @media screen {{
      body {{ background: #eef2f5; }}
      .report {{ margin: 16px auto; }}
    }}
    @media print {{
      html, body {{ background: #fff; }}
      .report {{ max-width: none; margin: 0; padding: 0; }}
      .summary-grid,
      .chart-grid,
      .scorecard-grid,
      .swot-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 900px) {{
      .summary-grid,
      .chart-grid,
      .scorecard-grid,
      .swot-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="report">
    {"".join(sections)}
  </main>
</body>
</html>
"""


def _build_report_spec(state: AgentState) -> ReportSpec:
    existing_report_spec = state.get("report_spec")
    if existing_report_spec is not None:
        if state.get("charts") and not existing_report_spec.charts:
            return existing_report_spec.model_copy(update={"charts": state["charts"]})
        return existing_report_spec

    final_judgment = state.get("final_judgment")
    if final_judgment is None:
        raise ValueError("Final judgment is required to assemble the report.")

    atomic_claims = []
    metric_claims = []
    for key in ("market_facts", "lges_facts", "catl_facts"):
        facts = state.get(key)
        if not facts:
            continue
        atomic_claims.extend(facts.atomic_claims)
        metric_claims.extend(facts.metric_claims)
    if not atomic_claims and not metric_claims:
        atomic_claims, metric_claims = _derive_legacy_claims(state)

    return ReportSpec(
        title="배터리 전략 비교 보고서",
        atomic_claims=atomic_claims,
        metric_claims=metric_claims,
        synthesis_claims=state.get("synthesis_claims", []),
        swot_matrix=state.get("swot_matrix", []),
        score_criteria=state.get("score_criteria", []),
        metric_comparison_rows=state.get("metric_comparison_rows", [])
        or state.get("profitability_reported_rows", []),
        charts=state.get("charts", []),
        final_judgment=final_judgment,
        references=state.get("document_manifest", []),
    )


def _derive_legacy_claims(state: AgentState) -> tuple[list[AtomicFactClaim], list[MetricFactClaim]]:
    atomic_claims: list[AtomicFactClaim] = []
    metric_claims: list[MetricFactClaim] = []
    market_context = state.get("market_context")
    if market_context is not None:
        market_refs = market_context.evidence_refs or state.get("citation_refs", [])[:1]
        market_findings = market_context.key_findings or [market_context.summary]
        for ordinal, item in enumerate(market_findings, start=1):
            atomic_claims.append(
                AtomicFactClaim(
                    scope="market",
                    category="market_overview" if ordinal == 1 else "policy_signal",
                    ordinal=ordinal,
                    claim_text=item,
                    evidence_refs=market_refs,
                )
            )
        for index, item in enumerate(market_context.comparison_axes, start=1):
            atomic_claims.append(
                AtomicFactClaim(
                    scope="market",
                    category="comparison_axis",
                    ordinal=index,
                    claim_text=item,
                    evidence_refs=market_refs,
                )
            )

    for scope, profile_key in (("lges", "lges_profile"), ("catl", "catl_profile")):
        profile = state.get(profile_key)
        if profile is None:
            continue
        evidence_refs = profile.evidence_refs or state.get("citation_refs", [])[:1]
        for ordinal, item in enumerate(profile.diversification_strategy, start=1):
            atomic_claims.append(
                AtomicFactClaim(
                    scope=scope,
                    category="diversification_strategy",
                    ordinal=ordinal,
                    claim_text=item,
                    evidence_refs=evidence_refs,
                )
            )
        for ordinal, item in enumerate(profile.regional_strategy, start=1):
            atomic_claims.append(
                AtomicFactClaim(
                    scope=scope,
                    category="regional_strategy",
                    ordinal=ordinal,
                    claim_text=item,
                    evidence_refs=evidence_refs,
                )
            )
        for ordinal, item in enumerate(profile.technology_strategy, start=1):
            atomic_claims.append(
                AtomicFactClaim(
                    scope=scope,
                    category="technology_strategy",
                    ordinal=ordinal,
                    claim_text=item,
                    evidence_refs=evidence_refs,
                )
            )
        for ordinal, item in enumerate(profile.risk_factors, start=1):
            atomic_claims.append(
                AtomicFactClaim(
                    scope=scope,
                    category="risk_factor",
                    ordinal=ordinal,
                    claim_text=item,
                    evidence_refs=evidence_refs,
                )
            )
        for ordinal, item in enumerate(profile.financial_indicators, start=1):
            metric_claims.append(
                MetricFactClaim(
                    scope=scope,
                    category=f"financial_indicator_{ordinal}",
                    ordinal=ordinal,
                    claim_text=f"{item.metric}: {item.value}",
                    metric_name=item.metric,
                    value=item.value,
                    evidence_refs=evidence_refs,
                )
            )
    return atomic_claims, metric_claims


def _build_claim_map(report_spec: ReportSpec) -> dict[str, AtomicFactClaim | MetricFactClaim]:
    return {
        claim.claim_id: claim
        for claim in [*report_spec.atomic_claims, *report_spec.metric_claims]
    }


def _render_summary_markdown(
    state: AgentState,
    report_spec: ReportSpec,
    manifest_map: dict,
    claim_map: dict,
) -> list[str]:
    summary_items = [
        f"목표: {state['goal']}",
        *[
            _with_supporting_citations(claim.claim_text, claim.supporting_claim_ids, manifest_map, claim_map)
            for claim in report_spec.synthesis_claims[:3]
        ],
        _with_supporting_citations(
            report_spec.final_judgment.judgment_text,
            report_spec.final_judgment.supporting_claim_ids,
            manifest_map,
            claim_map,
        ),
    ][:5]
    return _render_bullets(summary_items)


def _render_company_section_markdown(
    *,
    company_name: str,
    atomic_claims: list[AtomicFactClaim],
    metric_claims: list[MetricFactClaim],
    manifest_map: dict,
) -> list[str]:
    return [
        f"### {company_name} 핵심 주장",
        *_render_claim_section_markdown(atomic_claims, manifest_map),
        "",
        "### 정규화 이전 핵심 수치",
        *_render_metric_claims_markdown(metric_claims, manifest_map),
    ]


def _render_claim_section_markdown(
    claims: list[AtomicFactClaim],
    manifest_map: dict,
    *,
    fallback: list[str] | None = None,
) -> list[str]:
    if not claims:
        return _render_bullets(fallback or ["정보 부족"])
    return [
        f"- {_with_claim_citations(claim.claim_text, claim.evidence_refs, manifest_map)}"
        for claim in claims
    ]


def _render_metric_claims_markdown(
    metric_claims: list[MetricFactClaim],
    manifest_map: dict,
) -> list[str]:
    if not metric_claims:
        return ["- 정보 부족"]
    return [
        f"- {claim.metric_name}: {claim.value}{_inline_citations(claim.evidence_refs, manifest_map)}"
        for claim in metric_claims
    ]


def _render_metric_comparison_table_markdown(rows: list, manifest_map: dict) -> list[str]:
    lines = [
        "| 항목 | 기간 | LGES | CATL | 근거 |",
        "|---|---|---|---|---|",
    ]
    if not rows:
        lines.append("| 정보 부족 | - | - | - | - |")
        return lines
    for row in rows:
        lines.append(
            f"| {row.metric_name} | {row.period or '-'} | {row.lges_value or '-'} | "
            f"{row.catl_value or '-'} | {_format_citation_text(row.evidence_refs, manifest_map) or '-'} |"
        )
    return lines


def _render_chart_specs_markdown(charts: list[ChartSpec]) -> list[str]:
    if not charts:
        return ["- 정보 부족"]

    lines: list[str] = []
    for chart in charts:
        lines.append(f"### {chart.title}")
        periods = ", ".join(chart.x_axis_periods) or "-"
        lines.append(f"- X축: {periods}")
        lines.append(f"- Y축: {chart.y_axis_label}")
        for series in chart.series:
            values = ", ".join("-" if value is None else str(value) for value in series.values) or "-"
            lines.append(f"- {series.label}: {values}")
        lines.append("")
    return lines[:-1]


def _render_score_criteria_markdown(score_criteria: list[ScoreCriterion], manifest_map: dict) -> list[str]:
    grouped = _group_score_criteria(score_criteria)
    lines: list[str] = []
    for company_name, criteria in grouped:
        lines.append(f"### {company_name}")
        if not criteria:
            lines.append("- 정보 부족")
            lines.append("")
            continue
        for criterion in criteria:
            score_text = str(criterion.score) if criterion.score is not None else "정보 부족"
            lines.append(
                f"- {criterion.criterion_key}: {score_text} / 5 - "
                f"{criterion.rationale}{_inline_citations(criterion.evidence_refs, manifest_map)}"
            )
        lines.append("")
    return lines[:-1] if lines else ["- 정보 부족"]


def _render_final_judgment_markdown(
    report_spec: ReportSpec,
    manifest_map: dict,
    claim_map: dict,
) -> str:
    return _with_supporting_citations(
        report_spec.final_judgment.judgment_text,
        report_spec.final_judgment.supporting_claim_ids,
        manifest_map,
        claim_map,
    )


def _render_reference_lines(report_spec: ReportSpec, manifest_map: dict, claim_map: dict) -> list[str]:
    refs = _collect_report_references(report_spec, claim_map)
    if not refs:
        return ["1. 정보 부족"]
    lines = []
    for index, ref in enumerate(refs, start=1):
        label = manifest_map.get(ref.document_id)
        title = label.title if label else ref.document_id
        page = f", p.{ref.page}" if ref.page is not None else ""
        lines.append(f"{index}. {title}{page}")
    return lines


def _render_summary_card_html(line: str) -> str:
    label, _, value = line[2:].partition(": ")
    return f'<article class="card"><strong>{_html(label)}</strong><p>{_html(value or label)}</p></article>'


def _render_claim_section_html(claims, manifest_map, *, fallback=None) -> str:
    lines = _render_claim_section_markdown(claims, manifest_map, fallback=fallback)
    return _markdown_bullets_to_html(lines)


def _render_company_section_html(company_name, atomic_claims, metric_claims, manifest_map) -> str:
    return (
        f'<div class="panel"><h3>{_html(company_name)} 핵심 주장</h3>'
        f'{_markdown_bullets_to_html(_render_claim_section_markdown(atomic_claims, manifest_map))}'
        f'<h3>정규화 이전 핵심 수치</h3>'
        f'{_markdown_bullets_to_html(_render_metric_claims_markdown(metric_claims, manifest_map))}</div>'
    )


def _render_metric_comparison_table_html(rows, manifest_map) -> str:
    if not rows:
        return '<p class="empty">정보 부족</p>'
    body = "".join(
        f"<tr><td>{_html(row.metric_name)}</td><td>{_html(row.period or '-')}</td>"
        f"<td>{_html(row.lges_value or '-')}</td><td>{_html(row.catl_value or '-')}</td>"
        f"<td>{_html(_format_citation_text(row.evidence_refs, manifest_map) or '-')}</td></tr>"
        for row in rows
    )
    return (
        '<div class="comparison-panel"><table class="comparison-table"><thead><tr>'
        "<th>항목</th><th>기간</th><th>LGES</th><th>CATL</th><th>근거</th></tr>"
        f"</thead><tbody>{body}</tbody></table></div>"
    )


def _render_chart_specs_html(charts: list[ChartSpec]) -> str:
    if not charts:
        return '<p class="empty">정보 부족</p>'

    cards = []
    for chart in charts:
        headers = "".join(f"<th>{_html(period)}</th>" for period in chart.x_axis_periods)
        rows = "".join(
            "<tr>"
            f'<td class="chart-series-label">{_html(series.label)}</td>'
            + "".join(
                f"<td>{_html('-' if value is None else str(value))}</td>"
                for value in series.values
            )
            + "</tr>"
            for series in chart.series
        )
        cards.append(
            f"""
            <article class="chart-card">
              <h3>{_html(chart.title)}</h3>
              <p class="chart-meta">Y축: {_html(chart.y_axis_label)}</p>
              <table class="chart-table">
                <thead>
                  <tr>
                    <th>Series</th>
                    {headers}
                  </tr>
                </thead>
                <tbody>
                  {rows}
                </tbody>
              </table>
            </article>
            """
        )
    return f'<div class="chart-grid">{"".join(cards)}</div>'


def _render_score_criteria_html(score_criteria: list[ScoreCriterion], manifest_map: dict) -> str:
    grouped = _group_score_criteria(score_criteria)
    cards = []
    for company_name, criteria in grouped:
        if not criteria:
            cards.append(f'<article class="scorecard"><h3>{_html(company_name)}</h3><p class="empty">정보 부족</p></article>')
            continue
        body = "".join(
            f"<li>{_html(criterion.criterion_key)}: {_html(str(criterion.score) if criterion.score is not None else '정보 부족')} / 5"
            f" - {_html(criterion.rationale)} <span class=\"citation\">{_html(_format_citation_text(criterion.evidence_refs, manifest_map))}</span></li>"
            for criterion in criteria
        )
        cards.append(
            f'<article class="scorecard"><h3>{_html(company_name)}</h3><ul class="bullet-list">{body}</ul></article>'
        )
    return f'<div class="scorecard-grid">{"".join(cards)}</div>'


def _render_reference_html(report_spec: ReportSpec, manifest_map: dict, claim_map: dict) -> str:
    lines = _render_reference_lines(report_spec, manifest_map, claim_map)
    items = "".join(f"<li>{_html(line.partition('. ')[2] or line)}</li>" for line in lines)
    return f'<div class="reference-panel"><ol class="reference-list">{items}</ol></div>'


def _group_score_criteria(score_criteria: list[ScoreCriterion]) -> list[tuple[str, list[ScoreCriterion]]]:
    return [
        ("LG Energy Solution", [item for item in score_criteria if item.company_scope == "lges"]),
        ("CATL", [item for item in score_criteria if item.company_scope == "catl"]),
    ]


def _claims_for_scope(claims: list[AtomicFactClaim], scope: str) -> list[AtomicFactClaim]:
    return [claim for claim in claims if claim.scope == scope]


def _metric_claims_for_scope(claims: list[MetricFactClaim], scope: str) -> list[MetricFactClaim]:
    return [claim for claim in claims if claim.scope == scope]


def _with_claim_citations(text: str, evidence_refs: list[EvidenceRef], manifest_map: dict) -> str:
    citations = _inline_citations(evidence_refs, manifest_map)
    return f"{text}{citations}"


def _with_supporting_citations(text: str, supporting_claim_ids: list[str], manifest_map: dict, claim_map: dict) -> str:
    evidence_refs = []
    for claim_id in supporting_claim_ids:
        claim = claim_map.get(claim_id)
        if claim is not None:
            evidence_refs.extend(claim.evidence_refs)
    citations = _inline_citations(evidence_refs, manifest_map)
    return f"{text}{citations}"


def _inline_citations(evidence_refs: list[EvidenceRef], manifest_map: dict) -> str:
    citation_text = _format_citation_text(evidence_refs, manifest_map)
    return f" [{citation_text}]" if citation_text else ""


def _format_citation_text(evidence_refs: list[EvidenceRef], manifest_map: dict) -> str:
    seen = set()
    citations = []
    for ref in evidence_refs:
        key = (ref.document_id, ref.page)
        if key in seen:
            continue
        seen.add(key)
        document = manifest_map.get(ref.document_id)
        title = document.title if document else ref.document_id
        page = f" p.{ref.page}" if ref.page is not None else ""
        citations.append(f"{title}{page}")
        if len(citations) == 2:
            break
    return "; ".join(citations)


def _collect_report_references(report_spec: ReportSpec, claim_map: dict) -> list[EvidenceRef]:
    refs = []
    for claim in [*report_spec.atomic_claims, *report_spec.metric_claims]:
        refs.extend(claim.evidence_refs)
    for criterion in report_spec.score_criteria:
        refs.extend(criterion.evidence_refs)
    for claim_id in report_spec.final_judgment.supporting_claim_ids:
        claim = claim_map.get(claim_id)
        if claim is not None:
            refs.extend(claim.evidence_refs)
    unique = {}
    for ref in refs:
        unique[(ref.document_id, ref.chunk_id, ref.page)] = ref
    return list(unique.values())


def _markdown_bullets_to_html(lines: list[str]) -> str:
    if not lines:
        return '<p class="empty">정보 부족</p>'
    if len(lines) == 1 and lines[0] == "- 정보 부족":
        return '<p class="empty">정보 부족</p>'
    items = "".join(f"<li>{_html(line[2:])}</li>" for line in lines if line.startswith("- "))
    return f'<ul class="bullet-list">{items}</ul>'


def export_markdown_report(markdown: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def export_html_report(html: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def export_pdf_report(html: str, output_path: Path) -> None:
    if sync_playwright is None:
        raise ReportExportError(
            "playwright is not installed. Run `pip install -r requirements.txt` and "
            "`python -m playwright install chromium` to enable PDF export."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.emulate_media(media="print")
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=False,
                margin={
                    "top": "14mm",
                    "right": "12mm",
                    "bottom": "16mm",
                    "left": "12mm",
                },
            )
            browser.close()
    except Exception as exc:  # pragma: no cover - runtime/system dependency
        raise ReportExportError(
            "Playwright PDF export failed. Ensure Chromium is installed with "
            "`python -m playwright install chromium`."
        ) from exc


def mark_report_artifact_status(
    artifacts: list[ReportArtifact],
    *,
    artifact_type: str,
    path: Path,
    created: bool,
) -> list[ReportArtifact]:
    updated: list[ReportArtifact] = []
    matched = False
    for artifact in artifacts:
        if artifact.artifact_type == artifact_type and Path(artifact.path) == path:
            updated.append(artifact.model_copy(update={"created": created}))
            matched = True
        else:
            updated.append(artifact)
    if not matched:
        updated.append(
            ReportArtifact(artifact_type=artifact_type, path=str(path), created=created)
        )
    return updated


def _wrap_section(title: str, body_html: str, *, page_break: bool = False) -> str:
    page_break_class = " page-break" if page_break else ""
    return f"""
    <section class="section{page_break_class}">
      <div class="section-header">
        <h2>{_html(title)}</h2>
        <div class="section-rule"></div>
      </div>
      {body_html}
    </section>
    """


def _render_summary_cards(items: list[tuple[str, str]]) -> str:
    cards = "".join(
        f"""
        <article class="card">
          <span class="card-label">{_html(label)}</span>
          <p class="card-value">{_html(value)}</p>
        </article>
        """
        for label, value in items
    )
    return f'<section class="summary-grid">{cards}</section>'


def _render_company_section(profile) -> str:
    return f"""
    <div class="panel">
      <p class="company-lead">{_html(profile.business_overview)}</p>
      <div class="company-grid">
        <article class="panel">
          <h3>핵심 제품</h3>
          {_render_html_tag_list(profile.core_products)}
        </article>
        <article class="panel">
          <h3>다각화 전략</h3>
          {_render_html_list(profile.diversification_strategy)}
        </article>
        <article class="panel">
          <h3>지역 전략</h3>
          {_render_html_list(profile.regional_strategy)}
        </article>
        <article class="panel">
          <h3>기술 전략</h3>
          {_render_html_list(profile.technology_strategy)}
        </article>
      </div>
    </div>
    <div class="section-grid two-column compact-gap">
      <article class="panel">
        <h3>재무 지표</h3>
        {_render_financial_cards(profile.financial_indicators)}
      </article>
      <article class="panel">
        <h3>리스크 요인</h3>
        {_render_html_list(profile.risk_factors)}
      </article>
    </div>
    """


def _render_financial_cards(indicators: list) -> str:
    if not indicators:
        return '<p class="empty">정보 부족</p>'

    cards = "".join(
        f"""
        <article class="metric-card">
          <span class="meta-label">{_html(item.metric)}</span>
          <p>{_html(item.value)}</p>
        </article>
        """
        for item in indicators
    )
    return f'<div class="metric-grid">{cards}</div>'


def _render_comparison_table_html(rows: list) -> str:
    if not rows:
        return '<p class="empty">정보 부족</p>'

    body_rows = "".join(
        f"""
        <tr>
          <td>{_html(row.strategy_axis)}</td>
          <td>{_html(row.lges_value)}</td>
          <td>{_html(row.catl_value)}</td>
          <td>{_html(row.difference)}</td>
          <td>{_html(row.implication)}</td>
        </tr>
        """
        for row in rows
    )
    return f"""
    <div class="panel">
      <table class="comparison-table">
        <thead>
          <tr>
            <th>비교 축</th>
            <th>LGES</th>
            <th>CATL</th>
            <th>차이점</th>
            <th>시사점</th>
          </tr>
        </thead>
        <tbody>
          {body_rows}
        </tbody>
      </table>
    </div>
    """


def _render_swot_html(entries: list) -> str:
    if not entries:
        return '<p class="empty">정보 부족</p>'

    companies = []
    for entry in entries:
        companies.append(
            f"""
            <article class="company-block">
              <h3>{_html(entry.company_name)}</h3>
              <div class="swot-grid">
                {_render_swot_card("strength", "Strength", entry.strengths)}
                {_render_swot_card("weakness", "Weakness", entry.weaknesses)}
                {_render_swot_card("opportunity", "Opportunity", entry.opportunities)}
                {_render_swot_card("threat", "Threat", entry.threats)}
              </div>
            </article>
            """
        )
    return "".join(companies)


def _render_swot_card(kind: str, label: str, items: list[str]) -> str:
    return f"""
    <section class="swot-card {kind}">
      <span class="swot-kicker">{label}</span>
      {_render_html_list(items)}
    </section>
    """


def _render_scorecards_html(scorecards: list) -> str:
    if not scorecards:
        return '<p class="empty">정보 부족</p>'

    cards = "".join(
        f"""
        <article class="scorecard">
          <div class="scorecard-head">
            <div class="scorecard-title">{_html(card.company_name)}</div>
            <div class="scorecard-meta">5점 척도 기준</div>
          </div>
          {_render_score_bar("다각화 강도", card.diversification_strength)}
          {_render_score_bar("비용 경쟁력", card.cost_competitiveness)}
          {_render_score_bar("시장 적응력", card.market_adaptability)}
          {_render_score_bar("리스크 노출도", card.risk_exposure)}
          <p class="score-rationale">{_html(card.score_rationale)}</p>
        </article>
        """
        for card in scorecards
    )
    return f'<div class="scorecard-grid">{cards}</div>'


def _render_score_bar(label: str, value: int | None) -> str:
    percent = max(0, min(value or 0, 5)) * 20
    display = str(value) if value is not None else "정보 부족"
    return f"""
    <div class="score-row">
      <div class="score-label-row">
        <span class="score-label">{_html(label)}</span>
        <span class="score-value">{_html(display)}</span>
      </div>
      <div class="score-track">
        <div class="score-fill" style="width: {percent}%"></div>
      </div>
    </div>
    """


def _render_review_html(review_result, issues: list[str]) -> str:
    passed = bool(review_result and review_result.passed)
    issue_items = issues or ["추가 리뷰 이슈 없음"]
    status_class = "pass" if passed else "fail"
    status_text = "리뷰 통과" if passed else "리뷰 보완 필요"
    return f"""
    <div class="review-banner {status_class}">{status_text}</div>
    <div class="panel">
      <h3>리뷰 메모</h3>
      {_render_html_list(issue_items)}
    </div>
    """


def _render_references_html(state: AgentState) -> str:
    refs = _render_references(state)
    if refs == ["- 정보 부족"]:
        body = '<p class="empty">정보 부족</p>'
    else:
        items = "".join(f"<li>{_html(line[2:])}</li>" for line in refs)
        body = f'<ol class="reference-list">{items}</ol>'

    return f"""
    <div class="panel compact-gap">
      <h3>참고문헌</h3>
      {body}
    </div>
    """


def _render_html_list(items: list[str], *, class_name: str = "bullet-list") -> str:
    if not items:
        return '<p class="empty">정보 부족</p>'
    body = "".join(f"<li>{_html(item)}</li>" for item in items)
    return f'<ul class="{class_name}">{body}</ul>'


def _render_html_tag_list(items: list[str]) -> str:
    if not items:
        return '<p class="empty">정보 부족</p>'
    body = "".join(f'<li class="tag">{_html(item)}</li>' for item in items)
    return f'<ul class="tag-list">{body}</ul>'


def _render_bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- 정보 부족"]
    return [f"- {item}" for item in items]


def _render_financials(indicators: list) -> list[str]:
    if not indicators:
        return ["- 정보 부족"]
    return [f"- {item.metric}: {item.value}" for item in indicators]


def _render_comparison_table(rows: list) -> list[str]:
    lines = [
        "| 비교 축 | LGES | CATL | 차이점 | 시사점 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.strategy_axis} | {row.lges_value} | {row.catl_value} | {row.difference} | {row.implication} |"
        )
    return lines


def _render_swot(entries: list) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        lines.extend(
            [
                f"### {entry.company_name}",
                f"- 강점: {_join_or_default(entry.strengths)}",
                f"- 약점: {_join_or_default(entry.weaknesses)}",
                f"- 기회: {_join_or_default(entry.opportunities)}",
                f"- 위협: {_join_or_default(entry.threats)}",
                "",
            ]
        )
    return lines[:-1] if lines else ["- 정보 부족"]


def _render_scorecards(scorecards: list) -> list[str]:
    lines: list[str] = []
    for card in scorecards:
        lines.extend(
            [
                f"### {card.company_name}",
                f"- 다각화 강도: {_score_or_default(card.diversification_strength)}",
                f"- 비용 경쟁력: {_score_or_default(card.cost_competitiveness)}",
                f"- 시장 적응력: {_score_or_default(card.market_adaptability)}",
                f"- 리스크 노출도: {_score_or_default(card.risk_exposure)}",
                f"- 근거: {card.score_rationale}",
                "",
            ]
        )
    return lines[:-1] if lines else ["- 정보 부족"]


def _render_implications(comparison_matrix: list, scorecard: list) -> list[str]:
    implications = [row.implication for row in comparison_matrix[:3] if row.implication]
    implications.extend(
        f"{card.company_name}: {card.score_rationale}" for card in scorecard[:2]
    )
    return _render_bullets(implications)


def _render_references(state: AgentState) -> list[str]:
    manifest_map = {item.document_id: item for item in state.get("document_manifest", [])}
    refs = _collect_reference_items(state)
    if not refs:
        return ["- 정보 부족"]

    lines: list[str] = []
    for ref in refs:
        document = manifest_map.get(ref.document_id)
        title = document.title if document else ref.document_id
        page = f" p.{ref.page}" if ref.page is not None else ""
        chunk = f" ({ref.chunk_id})" if ref.chunk_id else ""
        lines.append(f"- {title}{page}{chunk}")
    return lines


def _collect_reference_items(state: AgentState) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    refs.extend(state["market_context"].evidence_refs)
    refs.extend(state["lges_profile"].evidence_refs)
    refs.extend(state["catl_profile"].evidence_refs)
    for row in state.get("comparison_matrix", []):
        refs.extend(row.evidence_refs)
    for entry in state.get("swot_matrix", []):
        refs.extend(entry.evidence_refs)
    for card in state.get("scorecard", []):
        refs.extend(card.evidence_refs)

    unique: dict[tuple[str, str | None, int | None], EvidenceRef] = {}
    for ref in refs:
        key = (ref.document_id, ref.chunk_id, ref.page)
        unique[key] = ref
    return list(unique.values())


def _join_or_default(values: list[str]) -> str:
    return ", ".join(values) if values else "정보 부족"


def _first_or_default(values: list[str]) -> str:
    return values[0] if values else "정보 부족"


def _score_or_default(value: int | None) -> str:
    return str(value) if value is not None else "정보 부족"


def _html(value: str) -> str:
    return escape(value, quote=True)

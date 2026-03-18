from __future__ import annotations

from pathlib import Path

from state import AgentState, EvidenceRef, ReportArtifact

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ImportError:  # pragma: no cover - handled at runtime
    A4 = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    getSampleStyleSheet = None


class ReportExportError(RuntimeError):
    """Raised when a report artifact cannot be exported."""


def assemble_markdown_report(state: AgentState) -> str:
    market_context = state["market_context"]
    lges_profile = state["lges_profile"]
    catl_profile = state["catl_profile"]
    comparison_matrix = state["comparison_matrix"]
    swot_matrix = state["swot_matrix"]
    scorecard = state["scorecard"]
    review_result = state.get("review_result")

    sections = [
        "# Battery Strategy Comparison Report",
        "",
        "## Summary",
        f"- Goal: {state['goal']}",
        f"- Market summary: {market_context.summary}",
        f"- LGES positioning: {_first_or_default(lges_profile.diversification_strategy)}",
        f"- CATL positioning: {_first_or_default(catl_profile.diversification_strategy)}",
        f"- Headline implication: {_first_or_default([row.implication for row in comparison_matrix])}",
        "",
        "## Market Background",
        market_context.summary,
        "",
        "### Key Findings",
        *_render_bullets(market_context.key_findings),
        "",
        "### Comparison Axes",
        *_render_bullets(market_context.comparison_axes),
        "",
        f"## {lges_profile.company_name}",
        f"### Business Overview\n{lges_profile.business_overview}",
        "",
        "### Core Products",
        *_render_bullets(lges_profile.core_products),
        "",
        "### Diversification Strategy",
        *_render_bullets(lges_profile.diversification_strategy),
        "",
        "### Regional Strategy",
        *_render_bullets(lges_profile.regional_strategy),
        "",
        "### Technology Strategy",
        *_render_bullets(lges_profile.technology_strategy),
        "",
        "### Financial Indicators",
        *_render_financials(lges_profile.financial_indicators),
        "",
        "### Risk Factors",
        *_render_bullets(lges_profile.risk_factors),
        "",
        f"## {catl_profile.company_name}",
        f"### Business Overview\n{catl_profile.business_overview}",
        "",
        "### Core Products",
        *_render_bullets(catl_profile.core_products),
        "",
        "### Diversification Strategy",
        *_render_bullets(catl_profile.diversification_strategy),
        "",
        "### Regional Strategy",
        *_render_bullets(catl_profile.regional_strategy),
        "",
        "### Technology Strategy",
        *_render_bullets(catl_profile.technology_strategy),
        "",
        "### Financial Indicators",
        *_render_financials(catl_profile.financial_indicators),
        "",
        "### Risk Factors",
        *_render_bullets(catl_profile.risk_factors),
        "",
        "## Comparison Matrix",
        *_render_comparison_table(comparison_matrix),
        "",
        "## SWOT",
        *_render_swot(swot_matrix),
        "",
        "## Scorecard",
        *_render_scorecards(scorecard),
        "",
        "## Implications",
        *_render_implications(comparison_matrix, scorecard),
        "",
        "## Review",
        f"- Passed: {'Yes' if review_result and review_result.passed else 'No'}",
        *_render_bullets(state.get("review_issues", []) or ["No outstanding review issues."]),
        "",
        "## References",
        *_render_references(state),
    ]
    return "\n".join(line for line in sections if line is not None).strip() + "\n"


def export_markdown_report(markdown: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def export_pdf_report(markdown: str, output_path: Path) -> None:
    if SimpleDocTemplate is None or Paragraph is None or Spacer is None:
        raise ReportExportError(
            "reportlab is not installed. Run `pip install -r requirements.txt` to enable PDF export."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading1"]))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], styles["Heading2"]))
        else:
            text = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if text.startswith("- "):
                text = f"&bull; {text[2:]}"
            story.append(Paragraph(text, styles["BodyText"]))
        story.append(Spacer(1, 4))
    doc.build(story)


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
        "| Axis | LGES | CATL | Difference | Implication |",
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
                f"- Strengths: {_join_or_default(entry.strengths)}",
                f"- Weaknesses: {_join_or_default(entry.weaknesses)}",
                f"- Opportunities: {_join_or_default(entry.opportunities)}",
                f"- Threats: {_join_or_default(entry.threats)}",
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
                f"- Diversification Strength: {_score_or_default(card.diversification_strength)}",
                f"- Cost Competitiveness: {_score_or_default(card.cost_competitiveness)}",
                f"- Market Adaptability: {_score_or_default(card.market_adaptability)}",
                f"- Risk Exposure: {_score_or_default(card.risk_exposure)}",
                f"- Rationale: {card.score_rationale}",
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

from __future__ import annotations

from dataclasses import dataclass, field

from tools.charting import missing_required_chart_ids
from state import (
    AgentState,
    CATL_REQUIRED_METRIC_FAMILIES,
    CATL_REQUIRED_RAW_METRIC_FAMILIES,
    ComparisonEvidenceOutput,
    LGES_REQUIRED_METRIC_FAMILIES,
    CATLFactExtractionOutput,
    FactExtractionOutput,
    LGESFactExtractionOutput,
    MetricFactClaim,
    ReportBlueprint,
    StructuredComparisonOutput,
)


@dataclass
class ValidationResult:
    hard_errors: list[str] = field(default_factory=list)
    soft_warnings: list[str] = field(default_factory=list)

    def add_hard_error(self, rule_key: str, message: str) -> None:
        self.hard_errors.append(f"[hard-gate:{rule_key}] {message}")

    def add_soft_warning(self, message: str) -> None:
        self.soft_warnings.append(message)


def validate_fact_extraction_output(
    scope: str,
    output: FactExtractionOutput,
) -> ValidationResult:
    result = ValidationResult()
    _validate_fact_claim_evidence(output, result)

    metric_families = output.metric_families()
    if scope == "lges":
        _add_missing_metric_family_errors(
            result,
            rule_key="lges-required-metric-family",
            owner_label="LGES",
            required=LGES_REQUIRED_METRIC_FAMILIES,
            actual=metric_families,
        )
    elif scope == "catl" and isinstance(output, CATLFactExtractionOutput):
        missing_required = set(CATL_REQUIRED_METRIC_FAMILIES) - metric_families
        if (
            missing_required == {"net_profit_margin"}
            and {"revenue", "profit_for_the_year"}.issubset(metric_families)
        ):
            missing_required = set()
        _add_missing_metric_family_errors(
            result,
            rule_key="catl-required-metric-family",
            owner_label="CATL",
            required=tuple(sorted(missing_required)),
            actual=set(),
        )

        missing_raw = set(CATL_REQUIRED_RAW_METRIC_FAMILIES) - metric_families
        if (
            missing_raw == {"net_profit_margin"}
            and {"revenue", "profit_for_the_year"}.issubset(metric_families)
        ):
            missing_raw = set()
        _add_missing_metric_family_errors(
            result,
            rule_key="catl-required-raw-metric-family",
            owner_label="CATL",
            required=tuple(sorted(missing_raw)),
            actual=set(),
        )

    return result


def validate_comparison_outputs(
    state: AgentState,
    output: ComparisonEvidenceOutput,
) -> ValidationResult:
    result = ValidationResult()
    allowed_claim_ids = (
        state["comparison_input_spec"].allowed_claim_ids()
        if state.get("comparison_input_spec")
        else set()
    )

    for claim in output.synthesis_claims:
        if len(claim.supporting_claim_ids) < 2:
            result.add_hard_error(
                "synthesis-support-count",
                f"SynthesisClaim '{claim.claim_id}' must reference at least two supporting_claim_ids.",
            )
        _validate_allowed_supporting_claim_ids(
            result,
            supporting_claim_ids=claim.supporting_claim_ids,
            allowed_claim_ids=allowed_claim_ids,
            label=f"SynthesisClaim '{claim.claim_id}'",
        )

    for criterion in output.score_criteria:
        if not criterion.evidence_refs:
            result.add_hard_error(
                "score-criterion-evidence",
                f"ScoreCriterion '{criterion.criterion_key}' is missing evidence_refs.",
            )
        _validate_allowed_supporting_claim_ids(
            result,
            supporting_claim_ids=criterion.supporting_claim_ids,
            allowed_claim_ids=allowed_claim_ids,
            label=f"ScoreCriterion '{criterion.criterion_key}'",
        )

    if not output.metric_comparison_rows:
        result.add_hard_error(
            "metric-comparison-rows-missing",
            "metric_comparison_rows is required for supervisor synthesis input.",
        )

    return result


def validate_report_blueprint(blueprint: ReportBlueprint) -> ValidationResult:
    result = ValidationResult()
    try:
        ReportBlueprint.model_validate(blueprint.model_dump(mode="json"))
    except Exception as exc:
        result.add_hard_error("blueprint-invalid", str(exc))
        return result
    if len(blueprint.comparison_axes) != 4:
        result.add_hard_error(
            "blueprint-comparison-axes",
            "comparison_axes must contain exactly four required axes.",
        )
    if not blueprint.comparability_precheck:
        result.add_hard_error(
            "blueprint-comparability-precheck",
            "comparability_precheck is required before worker routing.",
        )
    if not blueprint.worker_task_specs:
        result.add_hard_error(
            "blueprint-worker-task-specs",
            "worker_task_specs is required before worker routing.",
        )
    return result


def validate_final_delivery_state(state: AgentState) -> ValidationResult:
    result = ValidationResult()

    required_sections = (
        ("market_context", state.get("market_context")),
        ("lges_profile", state.get("lges_profile")),
        ("catl_profile", state.get("catl_profile")),
        ("report_blueprint", state.get("report_blueprint")),
        ("synthesis_claims", state.get("synthesis_claims")),
        ("supervisor_score_rationales", state.get("supervisor_score_rationales")),
        ("selected_comparison_rows", state.get("selected_comparison_rows")),
        ("supervisor_swot", state.get("supervisor_swot")),
        ("executive_summary", state.get("executive_summary")),
        ("implications", state.get("implications")),
        ("limitations", state.get("limitations")),
        ("metric_comparison_rows", state.get("metric_comparison_rows")),
        ("charts", state.get("chart_selection") or _resolve_charts(state)),
        ("final_judgment", state.get("final_judgment")),
        ("citation_refs", state.get("citation_refs")),
    )
    for section_name, value in required_sections:
        if not value:
            result.add_hard_error(
                "required-section-missing",
                f"{section_name} is required for final delivery.",
            )

    if state.get("supervisor_score_rationales") and not state.get("score_criteria"):
        result.add_hard_error(
            "no-fallback-ref-backfill",
            "supervisor score rationales exist without score_criteria; do not backfill evidence from citation_refs.",
        )
    if state.get("selected_comparison_rows") and not state.get("metric_comparison_rows"):
        result.add_hard_error(
            "no-fallback-ref-backfill",
            "selected comparison rows exist without metric_comparison_rows; do not backfill evidence from citation_refs.",
        )
    resolved_charts = _resolve_charts(state)
    if not resolved_charts:
        result.add_hard_error(
            "required-chart-missing",
            "at least one interpretable chart is required for final delivery.",
        )

    _add_summary_duplicate_warning(state, result)
    _add_generality_warning(state, result)
    _add_basis_mismatch_warning(state, result)
    _add_score_rationale_repeat_warning(state, result)
    _add_raw_metric_swot_warning(state, result)
    _add_trend_title_warning(resolved_charts, result)
    result.soft_warnings = list(dict.fromkeys(result.soft_warnings))

    return result


def _validate_fact_claim_evidence(
    output: FactExtractionOutput,
    result: ValidationResult,
) -> None:
    for claim in [*output.atomic_claims, *output.metric_claims]:
        if not claim.evidence_refs:
            result.add_hard_error(
                "fact-claim-evidence",
                f"{claim.__class__.__name__} '{claim.claim_id}' is missing evidence_refs.",
            )


def _add_missing_metric_family_errors(
    result: ValidationResult,
    *,
    rule_key: str,
    owner_label: str,
    required: tuple[str, ...],
    actual: set[str],
) -> None:
    missing = sorted(set(required) - actual) if actual else list(required)
    if not missing:
        return
    joined = ", ".join(missing)
    result.add_hard_error(
        rule_key,
        f"{owner_label} fact extraction is missing required metric families: {joined}",
    )


def _validate_allowed_supporting_claim_ids(
    result: ValidationResult,
    *,
    supporting_claim_ids: list[str],
    allowed_claim_ids: set[str],
    label: str,
) -> None:
    if not supporting_claim_ids:
        return
    unknown_claim_ids = sorted(set(supporting_claim_ids) - allowed_claim_ids)
    if unknown_claim_ids:
        joined = ", ".join(unknown_claim_ids)
        result.add_hard_error(
            "supporting-claim-origin",
            f"{label} references unknown supporting_claim_ids: {joined}",
        )


def _add_summary_duplicate_warning(state: AgentState, result: ValidationResult) -> None:
    market_context = state.get("market_context")
    final_judgment = state.get("final_judgment")
    if not market_context or not final_judgment:
        return
    summary = _normalize_text(market_context.summary)
    judgment = _normalize_text(final_judgment.judgment_text)
    if summary and summary == judgment:
        result.add_soft_warning(
            "Summary text exactly duplicates the final judgment."
        )


def _add_generality_warning(state: AgentState, result: ValidationResult) -> None:
    market_context = state.get("market_context")
    final_judgment = state.get("final_judgment")
    candidates = []
    if market_context:
        candidates.append(market_context.summary)
    if final_judgment:
        candidates.append(final_judgment.judgment_text)

    generic_markers = ("경쟁력", "전략", "확대", "강화", "다양화", "성장", "우위")
    for text in candidates:
        normalized = _normalize_text(text)
        if normalized and not any(char.isdigit() for char in text) and any(
            marker in text for marker in generic_markers
        ):
            result.add_soft_warning(
                "Summary or judgment may be too generic and lacks quantitative grounding."
            )
            return


def _add_basis_mismatch_warning(state: AgentState, result: ValidationResult) -> None:
    for row in state.get("metric_comparison_rows", []) or []:
        has_one_sided_value = bool(row.lges_value) ^ bool(row.catl_value)
        basis_note = (row.basis_note or "").strip().lower()
        if not has_one_sided_value:
            continue
        if "basis" in basis_note or "reported" in basis_note or "disclosed" in basis_note:
            continue
        result.add_soft_warning(
            f"MetricComparisonRow '{row.row_id}' may need an explanatory basis mismatch note."
        )


def _resolve_charts(state: AgentState) -> list:
    if "chart_selection" in state:
        return state.get("chart_selection", [])
    if state.get("charts"):
        return state.get("charts", [])
    report_spec = state.get("report_spec")
    if report_spec is not None:
        return report_spec.charts
    return []


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()


def _add_score_rationale_repeat_warning(state: AgentState, result: ValidationResult) -> None:
    rationales = [
        _normalize_text(item.rationale)
        for item in state.get("supervisor_score_rationales", []) or []
        if getattr(item, "rationale", None)
    ]
    repeated = {text for text in rationales if rationales.count(text) > 1 and text}
    if repeated:
        result.add_soft_warning(
            "Supervisor score rationales contain repeated template text and may be too generic."
        )


def _add_raw_metric_swot_warning(state: AgentState, result: ValidationResult) -> None:
    entries = state.get("supervisor_swot", []) or state.get("swot_matrix", [])
    metric_markers = ("revenue", "margin", "roe", "cash", "gwh", "bn", "%")
    for entry in entries:
        for text in [
            *(entry.strengths or []),
            *(entry.weaknesses or []),
            *(entry.opportunities or []),
            *(entry.threats or []),
        ]:
            normalized = _normalize_text(text)
            if (
                normalized
                and any(marker in normalized for marker in metric_markers)
                and not any(keyword in normalized for keyword in ("의미", "강점", "기회", "부담", "방어력", "전략"))
            ):
                result.add_soft_warning(
                    "SWOT entry may still read like a raw metric instead of a strategic interpretation."
                )
                return


def _add_trend_title_warning(charts: list, result: ValidationResult) -> None:
    for chart in charts or []:
        if "trend" in chart.title.lower() and len(chart.x_axis_periods) <= 1:
            result.add_soft_warning(
                f"Chart '{chart.title}' uses 'Trend' even though it has a single period."
            )
            return

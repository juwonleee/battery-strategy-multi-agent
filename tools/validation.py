from __future__ import annotations

from dataclasses import dataclass, field

from tools.charting import missing_required_chart_ids
from state import (
    AgentState,
    CATL_REQUIRED_METRIC_FAMILIES,
    CATL_REQUIRED_RAW_METRIC_FAMILIES,
    LGES_REQUIRED_METRIC_FAMILIES,
    CATLFactExtractionOutput,
    FactExtractionOutput,
    LGESFactExtractionOutput,
    MetricFactClaim,
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
    output: StructuredComparisonOutput,
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

    if len(output.final_judgment.supporting_claim_ids) < 2:
        result.add_hard_error(
            "final-judgment-support-count",
            "FinalJudgment must reference at least two supporting_claim_ids.",
        )
    _validate_allowed_supporting_claim_ids(
        result,
        supporting_claim_ids=output.final_judgment.supporting_claim_ids,
        allowed_claim_ids=allowed_claim_ids,
        label="FinalJudgment",
    )

    if not state.get("comparison_matrix"):
        result.add_hard_error(
            "comparison-matrix-missing",
            "comparison_matrix is required for final comparison delivery.",
        )
    if not state.get("swot_matrix"):
        result.add_hard_error(
            "swot-matrix-missing",
            "swot_matrix is required for final comparison delivery.",
        )
    if not state.get("scorecard"):
        result.add_hard_error(
            "scorecard-missing",
            "scorecard is required for final comparison delivery.",
        )
    if not output.metric_comparison_rows:
        result.add_hard_error(
            "metric-comparison-rows-missing",
            "metric_comparison_rows is required for final comparison delivery.",
        )
    if not output.final_judgment.judgment_text.strip():
        result.add_hard_error(
            "final-judgment-missing",
            "final_judgment is required for final comparison delivery.",
        )

    return result


def validate_final_delivery_state(state: AgentState) -> ValidationResult:
    result = ValidationResult()

    required_sections = (
        ("market_context", state.get("market_context")),
        ("lges_profile", state.get("lges_profile")),
        ("catl_profile", state.get("catl_profile")),
        ("comparison_matrix", state.get("comparison_matrix")),
        ("swot_matrix", state.get("swot_matrix")),
        ("scorecard", state.get("scorecard")),
        ("synthesis_claims", state.get("synthesis_claims")),
        ("score_criteria", state.get("score_criteria")),
        ("metric_comparison_rows", state.get("metric_comparison_rows")),
        ("charts", _resolve_charts(state)),
        ("final_judgment", state.get("final_judgment")),
        ("citation_refs", state.get("citation_refs")),
    )
    for section_name, value in required_sections:
        if not value:
            result.add_hard_error(
                "required-section-missing",
                f"{section_name} is required for final delivery.",
            )

    if state.get("scorecard") and not state.get("score_criteria"):
        result.add_hard_error(
            "no-fallback-ref-backfill",
            "scorecard exists without score_criteria; do not backfill evidence from citation_refs.",
        )
    if state.get("comparison_matrix") and not state.get("metric_comparison_rows"):
        result.add_hard_error(
            "no-fallback-ref-backfill",
            "comparison_matrix exists without metric_comparison_rows; do not backfill evidence from citation_refs.",
        )
    missing_chart_ids = missing_required_chart_ids(_resolve_charts(state))
    if missing_chart_ids:
        joined = ", ".join(missing_chart_ids)
        result.add_hard_error(
            "required-chart-missing",
            f"charts must include required chart_ids: {joined}",
        )

    _add_summary_duplicate_warning(state, result)
    _add_generality_warning(state, result)
    _add_basis_mismatch_warning(state, result)
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
    if state.get("charts"):
        return state.get("charts", [])
    report_spec = state.get("report_spec")
    if report_spec is not None:
        return report_spec.charts
    return []


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()

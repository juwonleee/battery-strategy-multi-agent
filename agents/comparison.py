from prompts import build_comparison_prompt
from pydantic import ValidationError

from state import AgentState, ComparisonEvidenceOutput
from tools.comparison_contract import (
    build_comparison_input_spec,
    build_legacy_comparison_artifacts,
)
from tools.comparison_fallback import build_fallback_comparison_evidence
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.validation import validate_comparison_outputs


def comparison_agent(state: AgentState) -> AgentState:
    """Generate comparison evidence packets for later supervisor-owned synthesis."""
    config = state["config"]

    try:
        comparison_input_spec = build_comparison_input_spec(state)
    except KeyError as exc:
        return {
            "status": "failed",
            "last_error": f"Missing first-pass claims required for comparison: {exc}",
        }

    prompt = build_comparison_prompt(
        goal=state["goal"],
        comparison_input_spec=comparison_input_spec,
    )

    try:
        extracted_output = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=ComparisonEvidenceOutput,
            max_output_tokens=max(config.openai_max_output_tokens, 4000),
        )
        output = ComparisonEvidenceOutput.model_validate(extracted_output)
    except (StructuredOutputError, ValidationError) as exc:
        output = build_fallback_comparison_evidence(
            state=state,
            comparison_input_spec=comparison_input_spec,
        )

    metric_comparison_rows = _merge_required_metric_rows(
        output.metric_comparison_rows,
        state.get("profitability_reported_rows", []),
    )

    comparison_state = {
        **state,
        "comparison_input_spec": comparison_input_spec,
        "metric_comparison_rows": metric_comparison_rows,
    }
    validation = validate_comparison_outputs(comparison_state, output)
    if validation.hard_errors:
        output = build_fallback_comparison_evidence(
            state=state,
            comparison_input_spec=comparison_input_spec,
        )
        metric_comparison_rows = _merge_required_metric_rows(
            output.metric_comparison_rows,
            state.get("profitability_reported_rows", []),
        )
        comparison_state = {
            **state,
            "comparison_input_spec": comparison_input_spec,
            "metric_comparison_rows": metric_comparison_rows,
        }
        validation = validate_comparison_outputs(comparison_state, output)
        if validation.hard_errors:
            return {
                "status": "failed",
                "last_error": validation.hard_errors[0],
            }
    legacy_artifacts = build_legacy_comparison_artifacts(output)

    return {
        "comparison_input_spec": comparison_input_spec,
        "synthesis_claims": output.synthesis_claims,
        "score_criteria": output.score_criteria,
        "metric_comparison_rows": metric_comparison_rows,
        "comparison_matrix": legacy_artifacts["comparison_matrix"],
        "low_confidence_claims": output.low_confidence_claims,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _merge_required_metric_rows(generated_rows, required_rows):
    merged = {row.row_id: row for row in generated_rows}
    for row in required_rows or []:
        merged.setdefault(row.row_id, row)
    return list(merged.values())

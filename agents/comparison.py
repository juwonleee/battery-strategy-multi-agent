from prompts import build_comparison_prompt
from pydantic import ValidationError

from state import AgentState, StructuredComparisonOutput
from tools.charting import build_chart_specs, missing_required_chart_ids
from tools.comparison_contract import (
    build_comparison_input_spec,
    build_legacy_comparison_artifacts,
    validate_structured_comparison_output,
)
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.validation import validate_comparison_outputs


def comparison_agent(state: AgentState) -> AgentState:
    """Generate second-pass comparison outputs from the first-pass claim catalog."""
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
            response_model=StructuredComparisonOutput,
            max_output_tokens=max(config.openai_max_output_tokens, 4000),
        )
        output = StructuredComparisonOutput.model_validate(extracted_output)
    except (StructuredOutputError, ValidationError) as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    validation_error = validate_structured_comparison_output(output, comparison_input_spec)
    if validation_error is not None:
        return {
            "status": "failed",
            "last_error": validation_error,
        }

    legacy_artifacts = build_legacy_comparison_artifacts(output)
    charts = build_chart_specs(
        lges_metrics=state.get("lges_normalized_metrics", []),
        catl_metrics=state.get("catl_normalized_metrics", []),
        metric_comparison_rows=output.metric_comparison_rows,
    )
    missing_chart_ids = missing_required_chart_ids(charts)
    if missing_chart_ids:
        joined = ", ".join(missing_chart_ids)
        return {
            "status": "failed",
            "last_error": f"Generated charts are missing required chart_ids: {joined}",
        }

    comparison_state = {
        **state,
        "comparison_input_spec": comparison_input_spec,
        "final_judgment": output.final_judgment,
        "metric_comparison_rows": output.metric_comparison_rows,
        "charts": charts,
        "comparison_matrix": legacy_artifacts["comparison_matrix"],
        "swot_matrix": legacy_artifacts["swot_matrix"],
        "scorecard": legacy_artifacts["scorecard"],
    }
    validation = validate_comparison_outputs(comparison_state, output)
    if validation.hard_errors:
        return {
            "status": "failed",
            "last_error": validation.hard_errors[0],
        }

    return {
        "comparison_input_spec": comparison_input_spec,
        "synthesis_claims": output.synthesis_claims,
        "score_criteria": output.score_criteria,
        "final_judgment": output.final_judgment,
        "metric_comparison_rows": output.metric_comparison_rows,
        "charts": charts,
        "comparison_matrix": legacy_artifacts["comparison_matrix"],
        "swot_matrix": legacy_artifacts["swot_matrix"],
        "scorecard": legacy_artifacts["scorecard"],
        "low_confidence_claims": output.low_confidence_claims,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }

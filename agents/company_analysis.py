from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from prompts import build_company_analysis_prompt
from state import AgentState
from tools.fact_conversion import build_company_profile_from_facts
from tools.normalization import MetricNormalizationError
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.validation import validate_fact_extraction_output


def run_company_analysis(
    state: AgentState,
    *,
    company_name: str,
    company_scope: str,
    evidence_refs: list,
    fact_output_model,
    required_metric_families: list[str],
    raw_metric_page_hints: list[int] | None = None,
    invoke_fn: Callable[..., Any] = invoke_structured_output,
    fallback_builder: Callable[[list], Any],
    normalize_metrics: Callable[[Any], list],
    profitability_row_builder: Callable[[list], list],
    facts_key: str,
    normalized_metrics_key: str,
    profile_key: str,
) -> AgentState:
    """Run the shared company fact-extraction pipeline for a single company worker."""
    config = state["config"]
    blueprint_questions = _resolve_blueprint_questions(state, worker_id=f"{company_scope}_analysis")
    prompt = build_company_analysis_prompt(
        company_name=company_name,
        company_scope=company_scope,
        goal=state["goal"],
        market_context_summary="\n".join(
            [state.get("market_context_summary", ""), *blueprint_questions]
        ).strip(),
        evidence_refs=evidence_refs,
        required_metric_families=required_metric_families,
        raw_metric_page_hints=raw_metric_page_hints,
    )

    try:
        extracted_output = invoke_fn(
            config=config,
            prompt=prompt,
            response_model=fact_output_model,
            max_output_tokens=max(config.openai_max_output_tokens, 4000),
        )
        facts = fact_output_model.model_validate(extracted_output)
    except (StructuredOutputError, ValidationError) as exc:
        try:
            facts = fallback_builder(evidence_refs)
        except (ValidationError, ValueError) as fallback_exc:
            return {
                "status": "failed",
                "last_error": f"{exc} | fallback failed: {fallback_exc}",
            }

    validation = validate_fact_extraction_output(company_scope, facts)
    if validation.hard_errors:
        return {
            "status": "failed",
            "last_error": validation.hard_errors[0],
        }

    try:
        profile = build_company_profile_from_facts(
            facts,
            company_name=company_name,
        )
        normalized_metrics = normalize_metrics(facts)
        profitability_reported_rows = profitability_row_builder(normalized_metrics)
    except MetricNormalizationError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    return {
        facts_key: facts,
        normalized_metrics_key: normalized_metrics,
        "profitability_reported_rows": profitability_reported_rows,
        profile_key: profile,
        "citation_refs": list(state.get("citation_refs", [])) + facts.source_evidence_refs,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _resolve_blueprint_questions(state: AgentState, *, worker_id: str) -> list[str]:
    blueprint = state.get("report_blueprint")
    if blueprint is None:
        return []
    for spec in blueprint.worker_task_specs:
        if spec.worker_id == worker_id:
            return list(spec.question_set)
    return []

from prompts import build_company_analysis_prompt
from pydantic import ValidationError

from state import AgentState, EvidenceRef, LGESFactExtractionOutput, LGES_REQUIRED_METRIC_FAMILIES
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.fact_fallbacks import build_lges_fallback_facts
from tools.fact_conversion import build_company_profile_from_facts
from tools.normalization import (
    MetricNormalizationError,
    build_profitability_reported_rows,
    normalize_lges_metrics,
)
from tools.validation import validate_fact_extraction_output


def lges_analysis_agent(state: AgentState) -> AgentState:
    """Generate an evidence-backed LGES company profile."""
    config = state["config"]
    retriever = _load_retriever(config)
    evidence_refs = _retrieve_lges_evidence(state, retriever)
    blueprint_questions = []
    blueprint = state.get("report_blueprint")
    if blueprint is not None:
        for spec in blueprint.worker_task_specs:
            if spec.worker_id == "lges_analysis":
                blueprint_questions = list(spec.question_set)
                break
    prompt = build_company_analysis_prompt(
        company_name="LG Energy Solution",
        company_scope="lges",
        goal=state["goal"],
        market_context_summary="\n".join(
            [state.get("market_context_summary", ""), *blueprint_questions]
        ).strip(),
        evidence_refs=evidence_refs,
        required_metric_families=list(LGES_REQUIRED_METRIC_FAMILIES),
    )

    try:
        extracted_output = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=LGESFactExtractionOutput,
            max_output_tokens=max(config.openai_max_output_tokens, 4000),
        )
        lges_facts = LGESFactExtractionOutput.model_validate(extracted_output)
    except (StructuredOutputError, ValidationError) as exc:
        try:
            lges_facts = build_lges_fallback_facts(evidence_refs)
        except (ValidationError, ValueError) as fallback_exc:
            return {
                "status": "failed",
                "last_error": f"{exc} | fallback failed: {fallback_exc}",
            }

    validation = validate_fact_extraction_output("lges", lges_facts)
    if validation.hard_errors:
        return {
            "status": "failed",
            "last_error": validation.hard_errors[0],
        }

    try:
        profile = build_company_profile_from_facts(
            lges_facts,
            company_name="LG Energy Solution",
        )
        lges_normalized_metrics = normalize_lges_metrics(lges_facts)
        profitability_reported_rows = build_profitability_reported_rows(
            lges_normalized_metrics,
            state.get("catl_normalized_metrics", []),
        )
    except MetricNormalizationError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    return {
        "lges_facts": lges_facts,
        "lges_normalized_metrics": lges_normalized_metrics,
        "profitability_reported_rows": profitability_reported_rows,
        "lges_profile": profile,
        "citation_refs": list(state.get("citation_refs", [])) + lges_facts.source_evidence_refs,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _retrieve_lges_evidence(state: AgentState, retriever) -> list[EvidenceRef]:
    queries = [
        "LG Energy Solution diversification strategy ESS 46 series LFP mid-nickel capex regional strategy",
        "LGES financial outlook EV slowdown ESS growth customer exposure investment priorities",
        "LG Energy Solution technology roadmap and risk factors in 2025",
        "LGES 2026 annual guidance revenue growth operating profit margin capex target financial outlook",
    ]
    evidence_map: dict[str, EvidenceRef] = {}
    for query in queries:
        for hit in retriever.retrieve(query, scope="lges", top_k=4):
            if hit.chunk_id:
                evidence_map[hit.chunk_id] = hit
    ranked = sorted(
        evidence_map.values(),
        key=lambda hit: (
            -(hit.score if hit.score is not None else float("-inf")),
            hit.page if hit.page is not None else 10**9,
            hit.chunk_id or "",
        ),
    )
    return ranked[:10]


def _load_retriever(config):
    from tools.retrieval import load_retriever

    return load_retriever(config)

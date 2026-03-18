from prompts import build_company_analysis_prompt
from pydantic import ValidationError

from state import (
    AgentState,
    CATL_REQUIRED_METRIC_FAMILIES,
    CATL_REQUIRED_RAW_PAGES,
    CATLFactExtractionOutput,
    EvidenceRef,
)
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.fact_fallbacks import build_catl_fallback_facts
from tools.fact_conversion import build_company_profile_from_facts
from tools.normalization import (
    MetricNormalizationError,
    build_profitability_reported_rows,
    normalize_catl_metrics,
)
from tools.validation import validate_fact_extraction_output


def catl_analysis_agent(state: AgentState) -> AgentState:
    """Generate an evidence-backed CATL company profile."""
    config = state["config"]
    retriever = _load_retriever(config)
    evidence_refs = _retrieve_catl_evidence(state, retriever)
    blueprint_questions = []
    blueprint = state.get("report_blueprint")
    if blueprint is not None:
        for spec in blueprint.worker_task_specs:
            if spec.worker_id == "catl_analysis":
                blueprint_questions = list(spec.question_set)
                break
    prompt = build_company_analysis_prompt(
        company_name="CATL",
        company_scope="catl",
        goal=state["goal"],
        market_context_summary="\n".join(
            [state.get("market_context_summary", ""), *blueprint_questions]
        ).strip(),
        evidence_refs=evidence_refs,
        required_metric_families=list(CATL_REQUIRED_METRIC_FAMILIES),
        raw_metric_page_hints=list(CATL_REQUIRED_RAW_PAGES),
    )

    try:
        extracted_output = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=CATLFactExtractionOutput,
            max_output_tokens=max(config.openai_max_output_tokens, 4000),
        )
        catl_facts = CATLFactExtractionOutput.model_validate(extracted_output)
    except (StructuredOutputError, ValidationError) as exc:
        try:
            catl_facts = build_catl_fallback_facts(evidence_refs)
        except (ValidationError, ValueError) as fallback_exc:
            return {
                "status": "failed",
                "last_error": f"{exc} | fallback failed: {fallback_exc}",
            }

    validation = validate_fact_extraction_output("catl", catl_facts)
    if validation.hard_errors:
        return {
            "status": "failed",
            "last_error": validation.hard_errors[0],
        }

    try:
        profile = build_company_profile_from_facts(
            catl_facts,
            company_name="CATL",
        )
        catl_normalized_metrics = normalize_catl_metrics(catl_facts)
        profitability_reported_rows = build_profitability_reported_rows(
            state.get("lges_normalized_metrics", []),
            catl_normalized_metrics,
        )
    except MetricNormalizationError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    return {
        "catl_facts": catl_facts,
        "catl_normalized_metrics": catl_normalized_metrics,
        "profitability_reported_rows": profitability_reported_rows,
        "catl_profile": profile,
        "citation_refs": list(state.get("citation_refs", [])) + catl_facts.source_evidence_refs,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _retrieve_catl_evidence(state: AgentState, retriever) -> list[EvidenceRef]:
    queries = [
        "CATL diversification strategy sodium-ion ESS ecosystem expansion global manufacturing competitive advantages",
        "CATL risk factors policy demand pricing competition supply chain and customer concentration",
        "CATL industry position market share technology roadmap and adjacent applications",
        "CATL revenue net profit margin ROE financial performance 2024 annual results earnings",
        "CATL cost structure gross margin battery materials recycling mineral resources business segment revenue breakdown",
        "CATL prospectus page 4 revenue profit for the year raw financial data",
        "CATL prospectus page 8 net profit margin gross profit margin raw financial data",
        "CATL prospectus page 9 ROE raw financial data",
        "CATL prospectus page 11 operating cash flow raw financial data",
        "CATL prospectus page 14 revenue profit for the year gross margin operating cash flow",
    ]
    evidence_map: dict[str, EvidenceRef] = {}
    for query in queries:
        for hit in retriever.retrieve(query, scope="catl", top_k=4):
            if hit.chunk_id:
                evidence_map[hit.chunk_id] = hit
    preferred_pages = set(CATL_REQUIRED_RAW_PAGES)
    ranked = sorted(
        evidence_map.values(),
        key=lambda hit: (
            0 if hit.page in preferred_pages else 1,
            -(hit.score if hit.score is not None else float("-inf")),
            hit.page if hit.page is not None else 10**9,
            hit.chunk_id or "",
        ),
    )
    return ranked[:12]


def _load_retriever(config):
    from tools.retrieval import load_retriever

    return load_retriever(config)

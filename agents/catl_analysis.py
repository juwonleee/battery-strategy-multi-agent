from agents.company_analysis import run_company_analysis
from state import (
    AgentState,
    CATL_REQUIRED_METRIC_FAMILIES,
    CATL_REQUIRED_RAW_PAGES,
    CATLFactExtractionOutput,
    EvidenceRef,
)
from tools.fact_fallbacks import build_catl_fallback_facts
from tools.normalization import (
    build_profitability_reported_rows,
    normalize_catl_metrics,
)
from tools.openai_client import invoke_structured_output


def catl_analysis_agent(state: AgentState) -> AgentState:
    """Generate an evidence-backed CATL company profile."""
    config = state["config"]
    retriever = _load_retriever(config)
    evidence_refs = _retrieve_catl_evidence(state, retriever)

    return run_company_analysis(
        state,
        company_name="CATL",
        company_scope="catl",
        evidence_refs=evidence_refs,
        fact_output_model=CATLFactExtractionOutput,
        required_metric_families=list(CATL_REQUIRED_METRIC_FAMILIES),
        raw_metric_page_hints=list(CATL_REQUIRED_RAW_PAGES),
        invoke_fn=invoke_structured_output,
        fallback_builder=build_catl_fallback_facts,
        normalize_metrics=normalize_catl_metrics,
        profitability_row_builder=lambda normalized_metrics: build_profitability_reported_rows(
            state.get("lges_normalized_metrics", []),
            normalized_metrics,
        ),
        facts_key="catl_facts",
        normalized_metrics_key="catl_normalized_metrics",
        profile_key="catl_profile",
    )


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

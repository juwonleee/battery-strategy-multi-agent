from agents.company_analysis import run_company_analysis
from state import AgentState, EvidenceRef, LGESFactExtractionOutput, LGES_REQUIRED_METRIC_FAMILIES
from tools.fact_fallbacks import build_lges_fallback_facts
from tools.normalization import (
    build_profitability_reported_rows,
    normalize_lges_metrics,
)
from tools.openai_client import invoke_structured_output


def lges_analysis_agent(state: AgentState) -> AgentState:
    """Generate an evidence-backed LGES company profile."""
    config = state["config"]
    retriever = _load_retriever(config)
    evidence_refs = _retrieve_lges_evidence(state, retriever)

    return run_company_analysis(
        state,
        company_name="LG Energy Solution",
        company_scope="lges",
        evidence_refs=evidence_refs,
        fact_output_model=LGESFactExtractionOutput,
        required_metric_families=list(LGES_REQUIRED_METRIC_FAMILIES),
        invoke_fn=invoke_structured_output,
        fallback_builder=build_lges_fallback_facts,
        normalize_metrics=normalize_lges_metrics,
        profitability_row_builder=lambda normalized_metrics: build_profitability_reported_rows(
            normalized_metrics,
            state.get("catl_normalized_metrics", []),
        ),
        facts_key="lges_facts",
        normalized_metrics_key="lges_normalized_metrics",
        profile_key="lges_profile",
    )


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

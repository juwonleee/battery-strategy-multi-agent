from prompts import build_company_analysis_prompt
from state import AgentState, CompanyProfile, EvidenceRef
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.retrieval import load_retriever


def lges_analysis_agent(state: AgentState) -> AgentState:
    """Generate an evidence-backed LGES company profile."""
    config = state["config"]
    retriever = load_retriever(config)
    evidence_refs = _retrieve_lges_evidence(state, retriever)
    prompt = build_company_analysis_prompt(
        company_name="LG Energy Solution",
        goal=state["goal"],
        market_context_summary=state.get("market_context_summary", ""),
        evidence_refs=evidence_refs,
    )

    try:
        profile = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=CompanyProfile,
        )
    except StructuredOutputError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    return {
        "lges_profile": profile,
        "citation_refs": list(state.get("citation_refs", [])) + evidence_refs,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _retrieve_lges_evidence(state: AgentState, retriever) -> list[EvidenceRef]:
    queries = [
        "LG Energy Solution diversification strategy ESS 46 series LFP mid-nickel capex regional strategy",
        "LGES financial outlook EV slowdown ESS growth customer exposure investment priorities",
        "LG Energy Solution technology roadmap and risk factors in 2025",
    ]
    evidence_map: dict[str, EvidenceRef] = {}
    for query in queries:
        for hit in retriever.retrieve(query, scope="lges", top_k=4):
            if hit.chunk_id:
                evidence_map[hit.chunk_id] = hit
    return list(evidence_map.values())

from prompts import build_company_analysis_prompt
from state import AgentState, CompanyProfile, EvidenceRef
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.retrieval import load_retriever


def catl_analysis_agent(state: AgentState) -> AgentState:
    """Generate an evidence-backed CATL company profile."""
    config = state["config"]
    retriever = load_retriever(config)
    evidence_refs = _retrieve_catl_evidence(state, retriever)
    prompt = build_company_analysis_prompt(
        company_name="CATL",
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
        "catl_profile": profile,
        "citation_refs": list(state.get("citation_refs", [])) + evidence_refs,
        "status": "running",
        "last_error": None,
    }


def _retrieve_catl_evidence(state: AgentState, retriever) -> list[EvidenceRef]:
    queries = [
        "CATL diversification strategy sodium-ion ESS ecosystem expansion global manufacturing competitive advantages",
        "CATL risk factors policy demand pricing competition supply chain and customer concentration",
        "CATL industry position market share technology roadmap and adjacent applications",
    ]
    evidence_map: dict[str, EvidenceRef] = {}
    for query in queries:
        for hit in retriever.retrieve(query, scope="catl", top_k=4):
            if hit.chunk_id:
                evidence_map[hit.chunk_id] = hit
    return list(evidence_map.values())

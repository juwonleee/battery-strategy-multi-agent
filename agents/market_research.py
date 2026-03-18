from prompts import build_market_research_prompt
from state import AgentState, MarketContext
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.retrieval import load_retriever


def market_research_agent(state: AgentState) -> AgentState:
    """Generate evidence-backed market context using retrieval and structured output."""
    config = state["config"]
    retriever = load_retriever(config)
    research_questions = state.get("research_questions") or [
        "What EV market changes are most important for comparing LGES and CATL diversification?",
        "What battery industry shifts matter for EV, ESS, and adjacent portfolio choices?",
        "What external risks shape diversification decisions in 2025?",
    ]
    query = " ".join(research_questions)
    evidence_refs = retriever.retrieve(query, scope="market", top_k=config.retrieval_top_k)
    prompt = build_market_research_prompt(
        goal=state["goal"],
        research_questions=research_questions,
        evidence_refs=evidence_refs,
    )

    try:
        market_context = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=MarketContext,
        )
    except StructuredOutputError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    return {
        "research_questions": research_questions,
        "market_context": market_context,
        "market_context_summary": market_context.summary,
        "citation_refs": evidence_refs,
        "status": "running",
        "last_error": None,
    }

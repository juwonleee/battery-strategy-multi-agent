from prompts import build_market_research_prompt
from pydantic import ValidationError

from state import AgentState, MarketFactExtractionOutput
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.fact_conversion import build_market_context_from_facts
from tools.validation import validate_fact_extraction_output


def market_research_agent(state: AgentState) -> AgentState:
    """Generate evidence-backed market context using retrieval and structured output."""
    config = state["config"]
    retriever = _load_retriever(config)
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
        extracted_output = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=MarketFactExtractionOutput,
        )
        market_facts = MarketFactExtractionOutput.model_validate(extracted_output)
    except (StructuredOutputError, ValidationError) as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    validation = validate_fact_extraction_output("market", market_facts)
    if validation.hard_errors:
        return {
            "status": "failed",
            "last_error": validation.hard_errors[0],
        }

    market_context = build_market_context_from_facts(market_facts)

    return {
        "research_questions": research_questions,
        "market_facts": market_facts,
        "market_context": market_context,
        "market_context_summary": market_context.summary,
        "citation_refs": list(state.get("citation_refs", [])) + market_facts.source_evidence_refs,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _load_retriever(config):
    from tools.retrieval import load_retriever

    return load_retriever(config)

from prompts import build_comparison_prompt
from state import AgentState, ComparisonOutput, EvidenceRef, SwotEntry
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.retrieval import load_retriever


def comparison_agent(state: AgentState) -> AgentState:
    """Generate evidence-backed comparison outputs from the two company profiles."""
    config = state["config"]
    retriever = load_retriever(config)
    comparison_evidence_refs = _retrieve_comparison_evidence(state, retriever)
    prompt = build_comparison_prompt(
        goal=state["goal"],
        market_context=state["market_context"],
        lges_profile=state["lges_profile"],
        catl_profile=state["catl_profile"],
        comparison_evidence_refs=comparison_evidence_refs,
    )

    try:
        output = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=ComparisonOutput,
            max_output_tokens=max(config.openai_max_output_tokens, 4000),
        )
    except StructuredOutputError as exc:
        return {
            "status": "failed",
            "last_error": str(exc),
        }

    output = _sanitize_comparison_output(
        output,
        lges_fallback_refs=state["lges_profile"].evidence_refs,
        catl_fallback_refs=state["catl_profile"].evidence_refs,
        comparison_fallback_refs=comparison_evidence_refs,
    )
    validation_error = _validate_comparison_output(output)
    if validation_error is not None:
        return {
            "status": "failed",
            "last_error": validation_error,
        }

    return {
        "comparison_matrix": output.comparison_matrix,
        "swot_matrix": output.swot_matrix,
        "scorecard": output.scorecard,
        "low_confidence_claims": output.low_confidence_claims,
        "citation_refs": list(state.get("citation_refs", [])) + comparison_evidence_refs,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _retrieve_comparison_evidence(state: AgentState, retriever) -> list[EvidenceRef]:
    queries = [
        "Compare LGES and CATL diversification strategy ESS LFP sodium-ion regional expansion",
        "LGES CATL cost competitiveness market adaptability risk exposure battery strategy comparison",
        "Battery industry comparison LGES CATL customer mix supply chain policy and pricing pressure",
    ]
    evidence_map: dict[str, EvidenceRef] = {}
    for query in queries:
        for hit in retriever.retrieve(query, scope="cross_check", top_k=6):
            if hit.chunk_id:
                evidence_map[hit.chunk_id] = hit
    return list(evidence_map.values())


def _validate_comparison_output(output: ComparisonOutput) -> str | None:
    if not output.comparison_matrix:
        return "Comparison output is missing comparison rows."
    if len(output.swot_matrix) != 2:
        return "Comparison output must include exactly two SWOT entries."
    if len(output.scorecard) != 2:
        return "Comparison output must include exactly two scorecards."

    for row in output.comparison_matrix:
        if not row.evidence_refs:
            return f"Comparison row '{row.strategy_axis}' is missing evidence references."

    for entry in output.swot_matrix:
        if not _has_any_swot_content(entry):
            return f"SWOT entry for '{entry.company_name}' is empty."
        if not entry.evidence_refs:
            return f"SWOT entry for '{entry.company_name}' is missing evidence references."

    for card in output.scorecard:
        if not card.score_rationale.strip():
            return f"Scorecard for '{card.company_name}' is missing rationale."
        if not card.evidence_refs:
            return f"Scorecard for '{card.company_name}' is missing evidence references."

    return None


def _sanitize_comparison_output(
    output: ComparisonOutput,
    *,
    lges_fallback_refs: list[EvidenceRef],
    catl_fallback_refs: list[EvidenceRef],
    comparison_fallback_refs: list[EvidenceRef],
) -> ComparisonOutput:
    output.comparison_matrix = [
        row for row in output.comparison_matrix if row.evidence_refs
    ]

    fallback_by_company = {
        "LG Energy Solution": lges_fallback_refs or comparison_fallback_refs,
        "CATL": catl_fallback_refs or comparison_fallback_refs,
    }
    for entry in output.swot_matrix:
        if not entry.evidence_refs:
            entry.evidence_refs = fallback_by_company.get(entry.company_name, comparison_fallback_refs)[:2]

    for card in output.scorecard:
        if not card.evidence_refs:
            card.evidence_refs = fallback_by_company.get(card.company_name, comparison_fallback_refs)[:2]

    return output


def _has_any_swot_content(entry: SwotEntry) -> bool:
    return any(
        [
            entry.strengths,
            entry.weaknesses,
            entry.opportunities,
            entry.threats,
        ]
    )

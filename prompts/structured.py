from __future__ import annotations

import json
from dataclasses import dataclass

from state import (
    ClaimTrace,
    ComparisonRow,
    CompanyProfile,
    EvidenceRef,
    MarketContext,
    ReviewResult,
    Scorecard,
    SwotEntry,
)


@dataclass(frozen=True)
class PromptBundle:
    name: str
    instructions: str
    input_text: str


COMMON_GUARDRAILS = """
You are generating structured analysis for a battery strategy comparison workflow.
- Use only the provided evidence snippets and context.
- If the evidence is insufficient, state "정보 부족" instead of guessing.
- Every substantive conclusion must map to the exact evidence references provided.
- Do not invent sources, pages, chunk IDs, or numerical values.
- Keep the response concise and decision-oriented.
""".strip()


def build_market_research_prompt(
    *,
    goal: str,
    research_questions: list[str],
    evidence_refs: list[EvidenceRef],
) -> PromptBundle:
    questions = research_questions or [
        "What market conditions matter most for comparing LGES and CATL diversification?",
        "Which external pressures shape portfolio choices in EV and ESS?",
    ]
    input_text = "\n\n".join(
        [
            f"Goal:\n{goal}",
            "Research questions:\n" + "\n".join(f"- {item}" for item in questions),
            "Evidence:\n" + serialize_evidence_refs(evidence_refs),
        ]
    )
    return PromptBundle(
        name="market_research",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "Return a MarketContext object with a concise summary, key findings, comparison axes, and evidence refs.",
                "Comparison axes should be reusable for both companies and phrased as short labels.",
            ]
        ),
        input_text=input_text,
    )


def build_company_analysis_prompt(
    *,
    company_name: str,
    goal: str,
    market_context_summary: str,
    evidence_refs: list[EvidenceRef],
) -> PromptBundle:
    input_text = "\n\n".join(
        [
            f"Goal:\n{goal}",
            f"Company:\n{company_name}",
            f"Market context summary:\n{market_context_summary or '정보 부족'}",
            "Evidence:\n" + serialize_evidence_refs(evidence_refs),
        ]
    )
    return PromptBundle(
        name=f"{company_name.lower().replace(' ', '_')}_analysis",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "Return a CompanyProfile object.",
                "Focus on business overview, diversification strategy, regional strategy, technology strategy, financial indicators, and risk factors.",
                "Lists should be short, concrete, and grounded in the evidence snippets.",
            ]
        ),
        input_text=input_text,
    )


def build_comparison_prompt(
    *,
    goal: str,
    market_context: MarketContext,
    lges_profile: CompanyProfile,
    catl_profile: CompanyProfile,
) -> PromptBundle:
    payload = {
        "goal": goal,
        "market_context": market_context.model_dump(mode="json"),
        "lges_profile": lges_profile.model_dump(mode="json"),
        "catl_profile": catl_profile.model_dump(mode="json"),
    }
    return PromptBundle(
        name="comparison",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "Compare the two company profiles using the same axes and evidence references.",
                "Produce comparison-ready reasoning that can later be mapped into comparison rows, SWOT entries, and scorecards.",
            ]
        ),
        input_text=json.dumps(payload, ensure_ascii=False, indent=2),
    )


def build_review_prompt(
    *,
    market_context_summary: str,
    comparison_matrix: list[ComparisonRow],
    swot_matrix: list[SwotEntry],
    scorecard: list[Scorecard],
    low_confidence_claims: list[ClaimTrace],
) -> PromptBundle:
    payload = {
        "market_context_summary": market_context_summary,
        "comparison_matrix": [row.model_dump(mode="json") for row in comparison_matrix],
        "swot_matrix": [row.model_dump(mode="json") for row in swot_matrix],
        "scorecard": [row.model_dump(mode="json") for row in scorecard],
        "low_confidence_claims": [
            item.model_dump(mode="json") for item in low_confidence_claims
        ],
    }
    return PromptBundle(
        name="review",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "Return a ReviewResult object.",
                "Mark passed=false if evidence links are weak, comparison axes are inconsistent, or score rationale is unsupported.",
                "If a revision target is needed, use one of: market_research, lges_analysis, catl_analysis, comparison.",
            ]
        ),
        input_text=json.dumps(payload, ensure_ascii=False, indent=2),
    )


def build_review_repair_prompt(
    *,
    review_result: ReviewResult,
    original_prompt: PromptBundle,
) -> PromptBundle:
    input_text = "\n\n".join(
        [
            f"Original prompt name:\n{original_prompt.name}",
            f"Original input:\n{original_prompt.input_text}",
            "Review result:\n"
            + json.dumps(review_result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        ]
    )
    return PromptBundle(
        name=f"{original_prompt.name}_repair",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "Revise the previous output according to the review result without introducing new unsupported claims.",
            ]
        ),
        input_text=input_text,
    )


def serialize_evidence_refs(evidence_refs: list[EvidenceRef], *, snippet_limit: int = 280) -> str:
    if not evidence_refs:
        return "- 정보 부족"

    lines: list[str] = []
    for item in evidence_refs:
        snippet = (item.snippet or "").replace("\n", " ").strip()
        if len(snippet) > snippet_limit:
            snippet = f"{snippet[:snippet_limit].rstrip()}..."
        lines.append(
            " | ".join(
                part
                for part in [
                    item.document_id,
                    item.chunk_id or "chunk_id:none",
                    f"page:{item.page}" if item.page is not None else None,
                    f"score:{item.score:.4f}" if item.score is not None else None,
                    snippet or "snippet:none",
                ]
                if part
            )
        )
    return "\n".join(f"- {line}" for line in lines)

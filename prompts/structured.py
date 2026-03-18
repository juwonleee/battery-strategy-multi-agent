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
- 모든 설명, 요약, 리스트 항목, 비교 문장, score rationale, review issue는 한국어로 작성한다.
- Use only the provided evidence snippets and context.
- If the evidence is insufficient, state "정보 부족" instead of guessing.
- Every substantive conclusion must map to the exact evidence references provided.
- When returning EvidenceRef objects, keep them minimal: prefer document_id, chunk_id, and page only.
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
        "LGES와 CATL의 다각화 전략 비교에서 가장 중요한 시장 조건은 무엇인가?",
        "EV와 ESS 포트폴리오 선택에 영향을 주는 외부 압력은 무엇인가?",
    ]
    input_text = "\n\n".join(
        [
            f"목표:\n{goal}",
            "연구 질문:\n" + "\n".join(f"- {item}" for item in questions),
            "근거:\n" + serialize_evidence_refs(evidence_refs),
        ]
    )
    return PromptBundle(
        name="market_research",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "MarketContext 객체를 반환한다.",
                "summary, key_findings, comparison_axes는 모두 한국어로 작성한다.",
                "comparison_axes는 두 기업 모두에 재사용 가능한 짧은 한국어 라벨로 작성한다.",
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
            f"목표:\n{goal}",
            f"기업명:\n{company_name}",
            f"시장 요약:\n{market_context_summary or '정보 부족'}",
            "근거:\n" + serialize_evidence_refs(evidence_refs),
        ]
    )
    return PromptBundle(
        name=f"{company_name.lower().replace(' ', '_')}_analysis",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "CompanyProfile 객체를 반환한다.",
                "business_overview, diversification_strategy, regional_strategy, technology_strategy, financial_indicators, risk_factors는 모두 한국어로 작성한다.",
                "리스트 항목은 짧고 구체적이어야 하며 제공된 근거에만 기반해야 한다.",
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
    comparison_evidence_refs: list[EvidenceRef],
) -> PromptBundle:
    payload = {
        "goal": goal,
        "market_context": market_context.model_dump(mode="json"),
        "lges_profile": lges_profile.model_dump(mode="json"),
        "catl_profile": catl_profile.model_dump(mode="json"),
        "comparison_evidence": [
            item.model_dump(mode="json") for item in comparison_evidence_refs
        ],
    }
    return PromptBundle(
        name="comparison",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "ComparisonOutput 객체를 반환한다.",
                "두 기업 프로필을 동일한 비교 축과 근거 기준으로 비교한다.",
                "3~5개의 comparison row를 만들고 strategy_axis와 implication은 짧은 한국어로 작성한다.",
                "SWOT entry는 정확히 2개여야 하며 LG Energy Solution 1개, CATL 1개를 만든다.",
                "scorecard는 정확히 2개여야 하며 LG Energy Solution 1개, CATL 1개를 만든다.",
                "SWOT 각 항목은 최대 3개 bullet 수준으로 제한하고, 각 row 또는 scorecard에는 1~3개의 evidence ref를 사용한다.",
                "각 점수는 1~5 또는 null이어야 하며, score_rationale은 비어 있지 않은 한국어 문장이어야 한다.",
                "근거가 약하거나 불완전하면 추정하지 말고 low_confidence_claims에 ClaimTrace를 추가한다.",
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
                "ReviewResult 객체를 반환한다.",
                "review_issues는 한국어로 작성한다.",
                "근거 연결이 약하거나 비교 축이 불일치하거나 score rationale이 근거로 뒷받침되지 않으면 passed=false로 표시한다.",
                "revision target이 필요하면 market_research, lges_analysis, catl_analysis, comparison 중 하나를 사용한다.",
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
            f"원본 프롬프트 이름:\n{original_prompt.name}",
            f"원본 입력:\n{original_prompt.input_text}",
            "리뷰 결과:\n"
            + json.dumps(review_result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        ]
    )
    return PromptBundle(
        name=f"{original_prompt.name}_repair",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "리뷰 결과를 반영해 이전 출력을 수정하되, 새로운 무근거 주장을 추가하지 않는다.",
            ]
        ),
        input_text=input_text,
    )


def serialize_evidence_refs(evidence_refs: list[EvidenceRef], *, snippet_limit: int = 500) -> str:
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

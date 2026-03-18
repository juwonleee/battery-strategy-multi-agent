from __future__ import annotations

import json
from dataclasses import dataclass

from state import (
    ClaimTrace,
    ComparisonRow,
    ComparisonEvidenceOutput,
    ComparisonInputSpec,
    CompanyProfile,
    EvidenceRef,
    FinalJudgment,
    MarketContext,
    ReportBlueprint,
    ReportSpec,
    ReviewResult,
    Scorecard,
    ScoreCriterion,
    SynthesisClaim,
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
                "MarketFactExtractionOutput 객체를 반환한다.",
                "자유형 시장 보고서가 아니라 1차 fact extraction만 수행한다.",
                "최종 보고서 문장, executive summary, final judgment, final SWOT prose를 작성하지 않는다.",
                "summary는 선택 필드이며 한두 문장 한국어 요약으로만 작성한다.",
                "atomic_claims의 category는 market_overview, demand_signal, policy_signal, risk_signal, comparison_axis 중 하나만 사용한다.",
                "comparison_axis category claim은 두 기업 모두에 재사용 가능한 짧은 한국어 비교 축으로 작성한다.",
                "각 atomic_claim과 metric_claim에는 evidence_refs를 최소 1개 포함한다.",
                "source_evidence_refs에는 실제로 사용한 상위 근거 ref만 넣는다.",
            ]
        ),
        input_text=input_text,
    )


def build_company_analysis_prompt(
    *,
    company_name: str,
    company_scope: str,
    goal: str,
    market_context_summary: str,
    evidence_refs: list[EvidenceRef],
    required_metric_families: list[str],
    raw_metric_page_hints: list[int] | None = None,
) -> PromptBundle:
    raw_page_text = (
        "없음"
        if not raw_metric_page_hints
        else ", ".join(str(page) for page in raw_metric_page_hints)
    )
    input_text = "\n\n".join(
        [
            f"목표:\n{goal}",
            f"기업명:\n{company_name}",
            f"기업 scope:\n{company_scope}",
            f"시장 요약:\n{market_context_summary or '정보 부족'}",
            "필수 metric family:\n" + "\n".join(f"- {item}" for item in required_metric_families),
            f"CATL raw page 힌트:\n{raw_page_text}",
            "근거:\n" + serialize_evidence_refs(evidence_refs, snippet_limit=220),
        ]
    )
    return PromptBundle(
        name=f"{company_name.lower().replace(' ', '_')}_analysis",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                f"{company_scope.upper()}FactExtractionOutput 객체를 반환한다.",
                "자유형 company profile을 쓰지 말고 1차 fact extraction만 수행한다.",
                "최종 요약, 최종 종합 판단, 최종 SWOT prose, 최종 score rationale은 작성하지 않는다.",
                "summary는 선택 필드이며 한두 문장 한국어 요약으로만 작성한다.",
                (
                    "atomic_claims category 규칙:\n"
                    "- business_overview\n"
                    "- core_product\n"
                    "- diversification_strategy\n"
                    "- regional_strategy\n"
                    "- technology_strategy\n"
                    "- risk_factor\n"
                    "- 위 6개 외 category는 사용하지 않는다."
                ),
                (
                    "metric_claims 작성 규칙:\n"
                    f"- category는 다음 필수 family 식별자 중 하나를 사용해야 한다: {', '.join(required_metric_families)}\n"
                    f"- 위 필수 family는 각각 최소 1개 이상 반드시 포함해야 한다.\n"
                    "- 필수 family를 하나라도 누락하면 실패로 간주한다.\n"
                    "- metric_name은 문서 표기 원문 이름을 최대한 유지한다.\n"
                    "- value는 숫자 또는 짧은 원문 값을 사용한다.\n"
                    "- reported_basis, period, unit은 문서에 있을 때만 채운다.\n"
                    "- 각 metric_claim에는 evidence_refs를 최소 1개 포함한다.\n"
                    "- 불필요하게 많은 metric_claim를 만들지 말고 필수 family 중심으로 간결하게 작성한다."
                ),
                "atomic_claims는 핵심 주장만 6개 이하로 제한한다.",
                "source_evidence_refs에는 실제로 사용한 상위 근거 ref만 넣는다.",
                (
                    "CATL인 경우 raw financial extraction 규칙:\n"
                    "- page 4, 8, 9, 11, 14를 우선 근거로 사용한다.\n"
                    "- revenue, profit for the year, net profit margin, gross profit margin, ROE, operating cash flow raw 값을 반드시 보존한다."
                ),
            ]
        ),
        input_text=input_text,
    )


def build_comparison_prompt(
    *,
    goal: str,
    comparison_input_spec: ComparisonInputSpec,
) -> PromptBundle:
    payload = {
        "goal": goal,
        "comparison_input_spec": comparison_input_spec.model_dump(mode="json"),
    }
    return PromptBundle(
        name="comparison",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "ComparisonEvidenceOutput 객체를 반환한다.",
                "입력으로 제공된 claim catalog만 사용해 supervisor synthesis를 위한 candidate evidence packet만 생성한다.",
                "최종 보고서 문장, final_judgment, final SWOT, 최종 scorecard rationale은 작성하지 않는다.",
                "raw evidence snippet이나 추가 검색 결과를 상정하지 말고, claim_id/claim_text/key_value/source_label/page_locator만 사용한다.",
                "synthesis_claims에는 claim_id 필드를 직접 쓰지 말고 생략한다. 코드가 deterministic claim_id를 자동 생성한다.",
                "3~5개의 synthesis_claim을 만들고 각 claim에는 supporting_claim_ids를 반드시 채운다.",
                "metric_comparison_rows는 claim catalog에서 직접 비교 가능한 수치/축만 사용한다.",
                "score_criteria는 criterion_key를 diversification_strength, cost_competitiveness, market_adaptability, risk_exposure 중 하나로 사용한다.",
                "ScoreCriterion의 company_scope는 lges 또는 catl만 사용하고, evidence_refs는 supporting_claim_ids에서 상속하지 말고 materialized field로 직접 채운다.",
                "근거가 약하거나 불완전하면 추정하지 말고 low_confidence_claims에 ClaimTrace를 추가한다.",
            ]
        ),
        input_text=json.dumps(payload, ensure_ascii=False, indent=2),
    )


def build_supervisor_blueprint_prompt(
    *,
    goal: str,
    target_companies: list[str],
    source_documents: list[dict[str, object]],
) -> PromptBundle:
    payload = {
        "goal": goal,
        "target_companies": target_companies,
        "source_documents": source_documents,
    }
    return PromptBundle(
        name="supervisor_blueprint",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "ReportBlueprint 객체를 반환한다.",
                "comparison_axes는 정확히 4개이며 다음 fixed order를 반드시 유지한다: portfolio_diversification, technology_product_strategy, regional_supply_chain, financial_resilience.",
                "comparability_precheck는 직접 비교 가능 여부를 metric 단위로 사전 판단한다.",
                "worker_task_specs는 market_research, lges_analysis, catl_analysis 세 worker만 정의한다.",
                "worker_task_specs의 forbidden_outputs에는 final_judgment, executive_summary, final_swot, final_score_rationale를 반드시 포함한다.",
                "결과 형식을 worker에게 위임하지 말고 evidence extraction 질문만 작성한다.",
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
    report_spec: ReportSpec,
    validation_warnings: list[str] | None = None,
) -> PromptBundle:
    payload = {
        "market_context_summary": market_context_summary,
        "comparison_matrix": [row.model_dump(mode="json") for row in comparison_matrix],
        "swot_matrix": [row.model_dump(mode="json") for row in swot_matrix],
        "scorecard": [row.model_dump(mode="json") for row in scorecard],
        "low_confidence_claims": [
            item.model_dump(mode="json") for item in low_confidence_claims
        ],
        "report_spec": report_spec.model_dump(mode="json"),
        "validation_warnings": list(validation_warnings or []),
    }
    return PromptBundle(
        name="review",
        instructions="\n\n".join(
            [
                COMMON_GUARDRAILS,
                "ReviewResult 객체를 반환한다.",
                "review_issues는 한국어로 작성한다.",
                "comparison_matrix, swot_matrix, scorecard뿐 아니라 report_spec 전체를 함께 검토한다.",
                "다음 항목을 우선순위로 점검한다: citation 누락, 점수 근거 부족, 결론-근거 불일치, summary exact duplicate, basis mismatch 설명 누락, 레이아웃상 필수 요소 누락.",
                "근거 연결이 약하거나 비교 축이 불일치하거나 score rationale이 근거로 뒷받침되지 않으면 passed=false로 표시한다.",
                "report_spec의 charts, metric_comparison_rows, score_criteria, final_judgment, references를 함께 대조해 누락/불일치 여부를 찾는다.",
                "validation_warnings가 제공되면 이를 참고하되 그대로 복사하지 말고 실제 검토 결과로 재기술한다.",
                "revision target이 필요하면 supervisor_synthesis, market_research, lges_analysis, catl_analysis, comparison 중 하나를 사용한다.",
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

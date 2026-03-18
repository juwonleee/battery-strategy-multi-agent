from __future__ import annotations

from pydantic import ValidationError

from prompts import build_supervisor_blueprint_prompt
from state import AgentState, ComparabilityPrecheckRow, ReportBlueprint, WorkerTaskSpec
from tools.openai_client import StructuredOutputError, invoke_structured_output
from tools.validation import validate_report_blueprint


def supervisor_blueprint_agent(state: AgentState) -> AgentState:
    """Create and validate the supervisor-owned report blueprint before any worker runs."""
    config = state["config"]
    prompt = build_supervisor_blueprint_prompt(
        goal=state["goal"],
        target_companies=state.get("target_companies", []),
        source_documents=[
            document.model_dump(mode="json") for document in state.get("source_documents", [])
        ],
    )

    try:
        blueprint = invoke_structured_output(
            config=config,
            prompt=prompt,
            response_model=ReportBlueprint,
            max_output_tokens=max(config.openai_max_output_tokens, 2000),
        )
        blueprint = ReportBlueprint.model_validate(blueprint)
    except (StructuredOutputError, ValidationError):
        blueprint = _build_fallback_blueprint(state)

    validation = validate_report_blueprint(blueprint)
    if validation.hard_errors:
        return {
            "status": "failed",
            "last_error": validation.hard_errors[0],
            "validation_warnings": validation.soft_warnings,
        }

    return {
        "report_blueprint": blueprint,
        "validation_warnings": validation.soft_warnings,
        "schema_retry_count": 0,
        "status": "running",
        "last_error": None,
    }


def _build_fallback_blueprint(state: AgentState) -> ReportBlueprint:
    return ReportBlueprint(
        comparison_axes=[
            "portfolio_diversification",
            "technology_product_strategy",
            "regional_supply_chain",
            "financial_resilience",
        ],
        comparability_precheck=[
            ComparabilityPrecheckRow(
                metric_name="revenue",
                company_scope="shared",
                period="reported",
                status="direct",
                reason="Both companies disclose revenue-related scale information that can be compared at a high level.",
            ),
            ComparabilityPrecheckRow(
                metric_name="profitability_reported",
                company_scope="shared",
                period="reported",
                status="reference_only",
                reason="Reported profitability basis differs across companies and should be treated as reference-only.",
            ),
            ComparabilityPrecheckRow(
                metric_name="secured_order_volume",
                company_scope="lges",
                period="reported",
                status="reference_only",
                reason="LGES discloses order-related metrics that do not have a directly aligned CATL pair.",
            ),
        ],
        worker_task_specs=[
            WorkerTaskSpec(
                worker_id="market_research",
                question_set=[
                    "배터리 산업 비교에 필요한 시장 배경과 외부 압력을 추출하라.",
                    "두 기업 모두에 재사용 가능한 비교 축 힌트를 추출하라.",
                ],
                required_output_fields=["atomic_claims", "metric_claims", "source_evidence_refs"],
                forbidden_outputs=[
                    "final_judgment",
                    "executive_summary",
                    "final_swot",
                    "final_score_rationale",
                ],
            ),
            WorkerTaskSpec(
                worker_id="lges_analysis",
                question_set=[
                    "LGES의 포트폴리오 다각화, 기술/제품, 지역 전략, 재무/리스크 근거를 추출하라."
                ],
                required_output_fields=["atomic_claims", "metric_claims", "source_evidence_refs"],
                forbidden_outputs=[
                    "final_judgment",
                    "executive_summary",
                    "final_swot",
                    "final_score_rationale",
                ],
            ),
            WorkerTaskSpec(
                worker_id="catl_analysis",
                question_set=[
                    "CATL의 포트폴리오 다각화, 기술/제품, 지역 전략, 재무/리스크 근거를 추출하라."
                ],
                required_output_fields=["atomic_claims", "metric_claims", "source_evidence_refs"],
                forbidden_outputs=[
                    "final_judgment",
                    "executive_summary",
                    "final_swot",
                    "final_score_rationale",
                ],
            ),
        ],
    )

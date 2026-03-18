from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator

if TYPE_CHECKING:
    from config import AppConfig


WorkflowStep = Literal[
    "supervisor_blueprint",
    "market_research",
    "lges_analysis",
    "catl_analysis",
    "comparison",
    "supervisor_synthesis",
    "review",
    "finish",
]

WorkflowStatus = Literal[
    "initialized",
    "routing",
    "running",
    "completed",
    "reviewed",
    "failed",
]

RevisionTarget = Literal[
    "supervisor_blueprint",
    "market_research",
    "lges_analysis",
    "catl_analysis",
    "comparison",
    "supervisor_synthesis",
]

SourceType = Literal[
    "company_report",
    "industry_report",
    "regulatory_filing",
    "speech",
    "presentation",
    "other",
]

CompanyScope = Literal["market", "lges", "catl", "shared"]
RetrievalScope = Literal["market", "lges", "catl", "cross_check"]
ClaimScope = Literal["market", "lges", "catl"]
ConfidenceLevel = Literal["high", "medium", "low"]
ComparisonAxis = Literal[
    "portfolio_diversification",
    "technology_product_strategy",
    "regional_supply_chain",
    "financial_resilience",
]
ComparabilityStatus = Literal["direct", "reference_only", "reject"]

_CLAIM_CATEGORY_PATTERN = re.compile(r"[^a-z0-9]+")


def normalize_claim_category(category: str) -> str:
    normalized = _CLAIM_CATEGORY_PATTERN.sub("_", category.strip().lower()).strip("_")
    if not normalized:
        raise ValueError("Claim category must contain at least one alphanumeric character.")
    return normalized


def build_claim_id(scope: ClaimScope, category: str, ordinal: int) -> str:
    if ordinal < 1:
        raise ValueError("Claim ordinal must be greater than or equal to 1.")
    return f"{scope}-{normalize_claim_category(category)}-{ordinal}"


class DocumentRef(BaseModel):
    document_id: str
    title: str
    source_path: str
    source_type: SourceType = "other"
    company_scope: CompanyScope = "shared"
    published_at: str | None = None
    page_range: str | None = None


class EvidenceRef(BaseModel):
    document_id: str
    chunk_id: str | None = None
    source_path: str | None = None
    page: int | None = None
    section_title: str | None = None
    snippet: str | None = None
    score: float | None = None


class ProcessedChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    source_path: str
    source_type: SourceType
    company_scope: CompanyScope
    published_at: str | None = None
    page: int
    text: str
    char_count: int = Field(ge=0)


class PreprocessingSummary(BaseModel):
    manifest_path: str
    processed_manifest_path: str
    processed_corpus_path: str
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    chunk_files: dict[str, str] = Field(default_factory=dict)


class RetryBudget(BaseModel):
    schema_validation_max: int = Field(default=2, ge=0)
    review_max: int = Field(default=2, ge=0)


class ExecutionLogEntry(BaseModel):
    timestamp: str
    step: WorkflowStep
    status: WorkflowStatus
    message: str
    attempt: int = Field(default=0, ge=0)


class ReportArtifact(BaseModel):
    artifact_type: Literal["markdown", "html", "pdf", "json", "log"]
    path: str
    created: bool = False


class MarketContext(BaseModel):
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    comparison_axes: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ComparabilityPrecheckRow(BaseModel):
    metric_name: str = Field(min_length=1)
    company_scope: Literal["lges", "catl", "shared"] = "shared"
    period: str | None = None
    status: ComparabilityStatus
    reason: str = Field(min_length=1)


class WorkerTaskSpec(BaseModel):
    worker_id: Literal["market_research", "lges_analysis", "catl_analysis"]
    question_set: list[str] = Field(default_factory=list, min_length=1)
    required_output_fields: list[str] = Field(default_factory=list, min_length=1)
    forbidden_outputs: list[str] = Field(default_factory=list, min_length=1)


class ReportBlueprint(BaseModel):
    comparison_axes: list[ComparisonAxis] = Field(default_factory=list, min_length=4, max_length=4)
    comparability_precheck: list[ComparabilityPrecheckRow] = Field(default_factory=list, min_length=1)
    worker_task_specs: list[WorkerTaskSpec] = Field(default_factory=list, min_length=3)

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "ReportBlueprint":
        expected_axes = [
            "portfolio_diversification",
            "technology_product_strategy",
            "regional_supply_chain",
            "financial_resilience",
        ]
        if self.comparison_axes != expected_axes:
            raise ValueError(
                "comparison_axes must exactly match the required fixed order: "
                + ", ".join(expected_axes)
            )
        required_forbidden = {
            "final_judgment",
            "executive_summary",
            "final_swot",
            "final_score_rationale",
        }
        worker_ids = {item.worker_id for item in self.worker_task_specs}
        if worker_ids != {"market_research", "lges_analysis", "catl_analysis"}:
            raise ValueError(
                "worker_task_specs must define exactly market_research, lges_analysis, and catl_analysis."
            )
        for item in self.worker_task_specs:
            if not required_forbidden.issubset(set(item.forbidden_outputs)):
                missing = sorted(required_forbidden - set(item.forbidden_outputs))
                raise ValueError(
                    f"worker_task_spec '{item.worker_id}' is missing required forbidden outputs: {', '.join(missing)}"
                )
        return self


class ClaimBase(BaseModel):
    scope: ClaimScope
    category: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    claim_id: str | None = None

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        return normalize_claim_category(value)

    @model_validator(mode="after")
    def _set_claim_id(self) -> ClaimBase:
        expected_claim_id = build_claim_id(self.scope, self.category, self.ordinal)
        if self.claim_id is None:
            self.claim_id = expected_claim_id
            return self
        if self.claim_id != expected_claim_id:
            raise ValueError(
                "claim_id must match the deterministic format "
                f"'{expected_claim_id}' for the supplied scope/category/ordinal."
            )
        return self


class AtomicFactClaim(ClaimBase):
    claim_text: str = Field(min_length=1)
    evidence_refs: list[EvidenceRef] = Field(..., min_length=1)


class MetricFactClaim(ClaimBase):
    claim_text: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    normalized_metric_name: str | None = None
    reported_basis: str | None = None
    period: str | None = None
    value: str | float | int
    unit: str | None = None
    evidence_refs: list[EvidenceRef] = Field(..., min_length=1)


class SynthesisClaim(ClaimBase):
    claim_text: str = Field(min_length=1)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = "medium"


class FinalJudgment(BaseModel):
    judgment_text: str = Field(min_length=1)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = "medium"


class ScoreCriterion(BaseModel):
    criterion_key: str = Field(min_length=1)
    company_scope: Literal["lges", "catl"]
    score: int | None = Field(default=None, ge=1, le=5)
    rationale: str = Field(min_length=1)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(
        ...,
        min_length=1,
        description=(
            "Materialized evidence refs for this criterion. "
            "Do not infer or inherit them from supporting_claim_ids."
        ),
    )


class MetricComparisonRow(BaseModel):
    row_id: str = Field(min_length=1)
    row_group: str | None = None
    metric_name: str = Field(min_length=1)
    period: str | None = None
    lges_value: str | None = None
    catl_value: str | None = None
    basis_note: str | None = None
    comparability_status: ComparabilityStatus | None = None
    interpretation: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ChartSeries(BaseModel):
    label: str = Field(min_length=1)
    values: list[float | None] = Field(default_factory=list)
    source_row_ids: list[str] = Field(default_factory=list)


class ChartSpec(BaseModel):
    chart_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    series: list[ChartSeries] = Field(default_factory=list)
    x_axis_periods: list[str] = Field(default_factory=list)
    y_axis_label: str = Field(min_length=1)
    interpretation: str | None = None
    caution_note: str | None = None


class ReportSpec(BaseModel):
    title: str = Field(min_length=1)
    executive_summary: list[str] = Field(default_factory=list)
    comparison_framework: list[str] = Field(default_factory=list)
    lges_strategy_summary: list[str] = Field(default_factory=list)
    catl_strategy_summary: list[str] = Field(default_factory=list)
    quick_comparison_panel: list["ComparisonRow"] = Field(default_factory=list)
    selected_comparison_rows: list[MetricComparisonRow] = Field(default_factory=list)
    reference_only_rows: list[MetricComparisonRow] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    atomic_claims: list[AtomicFactClaim] = Field(default_factory=list)
    metric_claims: list[MetricFactClaim] = Field(default_factory=list)
    synthesis_claims: list[SynthesisClaim] = Field(default_factory=list)
    swot_matrix: list[SwotEntry] = Field(default_factory=list)
    score_criteria: list[ScoreCriterion] = Field(default_factory=list)
    metric_comparison_rows: list[MetricComparisonRow] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    final_judgment: FinalJudgment | None = None
    references: list[DocumentRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_claim_ids(self) -> ReportSpec:
        claim_ids = [
            claim.claim_id
            for claim in [
                *self.atomic_claims,
                *self.metric_claims,
                *self.synthesis_claims,
            ]
        ]
        duplicates = sorted(
            {claim_id for claim_id in claim_ids if claim_ids.count(claim_id) > 1}
        )
        if duplicates:
            joined = ", ".join(duplicates)
            raise ValueError(f"ReportSpec claim_id values must be unique: {joined}")
        return self


LGES_REQUIRED_METRIC_FAMILIES = (
    "revenue_growth_guidance",
    "operating_margin_guidance_or_actual",
    "capex",
    "ess_capacity",
    "secured_order_volume",
)

CATL_REQUIRED_METRIC_FAMILIES = (
    "revenue",
    "gross_profit_margin",
    "net_profit_margin",
    "roe",
    "operating_cash_flow",
)

CATL_REQUIRED_RAW_METRIC_FAMILIES = (
    "revenue",
    "profit_for_the_year",
    "net_profit_margin",
    "gross_profit_margin",
    "roe",
    "operating_cash_flow",
)

CATL_REQUIRED_RAW_PAGES = (4, 8, 9, 11, 14)


class FactExtractionOutput(BaseModel):
    scope: ClaimScope
    summary: str | None = None
    atomic_claims: list[AtomicFactClaim] = Field(default_factory=list)
    metric_claims: list[MetricFactClaim] = Field(default_factory=list)
    source_evidence_refs: list[EvidenceRef] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_claim_scope_alignment(self) -> FactExtractionOutput:
        for claim in [*self.atomic_claims, *self.metric_claims]:
            if claim.scope != self.scope:
                raise ValueError(
                    f"Claim '{claim.claim_id}' scope '{claim.scope}' does not match "
                    f"extraction scope '{self.scope}'."
                )
        return self

    def metric_families(self) -> set[str]:
        return {claim.category for claim in self.metric_claims}


class MarketFactExtractionOutput(FactExtractionOutput):
    scope: Literal["market"] = "market"


class LGESFactExtractionOutput(FactExtractionOutput):
    scope: Literal["lges"] = "lges"

    @model_validator(mode="after")
    def _validate_required_metric_families(self) -> LGESFactExtractionOutput:
        missing = sorted(set(LGES_REQUIRED_METRIC_FAMILIES) - self.metric_families())
        if missing:
            joined = ", ".join(missing)
            raise ValueError(
                f"LGES fact extraction is missing required metric families: {joined}"
            )
        return self


class CATLFactExtractionOutput(FactExtractionOutput):
    scope: Literal["catl"] = "catl"

    @model_validator(mode="after")
    def _validate_required_metric_families(self) -> CATLFactExtractionOutput:
        metric_families = self.metric_families()
        missing = set(CATL_REQUIRED_METRIC_FAMILIES) - metric_families
        if (
            missing == {"net_profit_margin"}
            and {"revenue", "profit_for_the_year"}.issubset(metric_families)
        ):
            missing = set()
        missing_list = sorted(missing)
        if missing_list:
            joined = ", ".join(missing_list)
            raise ValueError(
                f"CATL fact extraction is missing required metric families: {joined}"
            )
        missing_raw = set(CATL_REQUIRED_RAW_METRIC_FAMILIES) - metric_families
        if (
            missing_raw == {"net_profit_margin"}
            and {"revenue", "profit_for_the_year"}.issubset(metric_families)
        ):
            missing_raw = set()
        missing_raw_list = sorted(missing_raw)
        if missing_raw_list:
            joined = ", ".join(missing_raw_list)
            raise ValueError(
                f"CATL fact extraction is missing required raw metric families: {joined}"
            )
        return self


class NormalizedMetric(BaseModel):
    scope: Literal["lges", "catl"]
    normalized_metric_name: str = Field(min_length=1)
    reported_basis: str = Field(min_length=1)
    period: str = Field(min_length=1)
    value: float | str
    numeric_value: float | None = None
    unit: str | None = None
    source_claim_ids: list[str] = Field(..., min_length=1)
    evidence_refs: list[EvidenceRef] = Field(..., min_length=1)
    is_derived: bool = False
    derivation_note: str | None = None


class ComparisonInputClaim(BaseModel):
    claim_id: str = Field(min_length=1)
    scope: ClaimScope
    category: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    key_value: str | None = None
    source_label: str = Field(min_length=1)
    page_locator: str = Field(min_length=1)


class CompanyClaimCatalog(BaseModel):
    owner_scope: Literal["lges", "catl"]
    claims: list[ComparisonInputClaim] = Field(default_factory=list, max_length=12)


class ComparisonInputSpec(BaseModel):
    lges_catalog: CompanyClaimCatalog
    catl_catalog: CompanyClaimCatalog

    def allowed_claim_ids(self) -> set[str]:
        return {
            claim.claim_id
            for claim in [
                *self.lges_catalog.claims,
                *self.catl_catalog.claims,
            ]
        }


class StructuredComparisonOutput(BaseModel):
    synthesis_claims: list[SynthesisClaim] = Field(default_factory=list)
    score_criteria: list[ScoreCriterion] = Field(default_factory=list)
    swot_matrix: list[SwotEntry] = Field(default_factory=list)
    final_judgment: FinalJudgment
    metric_comparison_rows: list[MetricComparisonRow] = Field(default_factory=list)
    low_confidence_claims: list[ClaimTrace] = Field(default_factory=list)


class ComparisonEvidenceOutput(BaseModel):
    synthesis_claims: list[SynthesisClaim] = Field(default_factory=list)
    score_criteria: list[ScoreCriterion] = Field(default_factory=list)
    metric_comparison_rows: list[MetricComparisonRow] = Field(default_factory=list)
    low_confidence_claims: list[ClaimTrace] = Field(default_factory=list)


class FinancialIndicator(BaseModel):
    metric: str
    value: str


class CompanyProfile(BaseModel):
    company_name: str
    business_overview: str
    core_products: list[str] = Field(default_factory=list)
    diversification_strategy: list[str] = Field(default_factory=list)
    regional_strategy: list[str] = Field(default_factory=list)
    technology_strategy: list[str] = Field(default_factory=list)
    financial_indicators: list[FinancialIndicator] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    strategy_axis: str
    lges_value: str
    catl_value: str
    difference: str
    implication: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SwotEntry(BaseModel):
    company_name: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class Scorecard(BaseModel):
    company_name: str
    diversification_strength: int | None = Field(default=None, ge=1, le=5)
    cost_competitiveness: int | None = Field(default=None, ge=1, le=5)
    market_adaptability: int | None = Field(default=None, ge=1, le=5)
    risk_exposure: int | None = Field(default=None, ge=1, le=5)
    score_rationale: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ClaimTrace(BaseModel):
    claim: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence_level: Literal["high", "medium", "low"]


class ComparisonOutput(BaseModel):
    comparison_matrix: list[ComparisonRow] = Field(default_factory=list)
    swot_matrix: list[SwotEntry] = Field(default_factory=list)
    scorecard: list[Scorecard] = Field(default_factory=list)
    low_confidence_claims: list[ClaimTrace] = Field(default_factory=list)


class ReviewResult(BaseModel):
    passed: bool
    revision_target: RevisionTarget | None = None
    review_issues: list[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    goal: str
    target_companies: list[str]
    config: AppConfig
    research_questions: list[str]
    source_documents: list[DocumentRef]
    document_manifest: list[DocumentRef]
    preprocessing_summary: PreprocessingSummary
    retrieval_handles: dict[str, str]
    report_blueprint: ReportBlueprint
    market_facts: MarketFactExtractionOutput
    lges_facts: LGESFactExtractionOutput
    catl_facts: CATLFactExtractionOutput
    lges_normalized_metrics: list[NormalizedMetric]
    catl_normalized_metrics: list[NormalizedMetric]
    profitability_reported_rows: list[MetricComparisonRow]
    comparison_input_spec: ComparisonInputSpec
    synthesis_claims: list[SynthesisClaim]
    score_criteria: list[ScoreCriterion]
    comparability_decisions: list[MetricComparisonRow]
    final_judgment: FinalJudgment
    metric_comparison_rows: list[MetricComparisonRow]
    charts: list[ChartSpec]
    selected_comparison_rows: list[MetricComparisonRow]
    reference_only_rows: list[MetricComparisonRow]
    chart_selection: list[ChartSpec]
    executive_summary: list[str]
    company_strategy_summaries: dict[str, list[str]]
    quick_comparison_panel: list[ComparisonRow]
    supervisor_swot: list[SwotEntry]
    supervisor_score_rationales: list[ScoreCriterion]
    implications: list[str]
    limitations: list[str]
    report_spec: ReportSpec
    market_context: MarketContext
    market_context_summary: str
    lges_profile: CompanyProfile
    catl_profile: CompanyProfile
    comparison_matrix: list[ComparisonRow]
    swot_matrix: list[SwotEntry]
    scorecard: list[Scorecard]
    citation_refs: list[EvidenceRef]
    low_confidence_claims: list[ClaimTrace]
    review_result: ReviewResult
    review_issues: list[str]
    validation_warnings: list[str]
    retry_budget: RetryBudget
    report_artifacts: list[ReportArtifact]
    execution_log: list[ExecutionLogEntry]
    schema_retry_count: int
    review_retry_count: int
    current_step: WorkflowStep
    routing_reason: str | None
    status: WorkflowStatus
    last_error: str | None


def build_initial_state(
    config: AppConfig,
    *,
    source_documents: list[DocumentRef] | None = None,
    retrieval_handles: dict[str, str] | None = None,
    preprocessing_summary: PreprocessingSummary | None = None,
) -> AgentState:
    manifest_documents = list(source_documents or [])
    log_entry = ExecutionLogEntry(
        timestamp=_utc_now_iso(),
        step="market_research",
        status="initialized",
        message="Initial workflow state created.",
    )
    return {
        "goal": "LGES와 CATL의 다각화 전략을 비교 분석한다",
        "target_companies": ["LG Energy Solution", "CATL"],
        "config": config,
        "research_questions": [],
        "source_documents": manifest_documents,
        "document_manifest": manifest_documents,
        "preprocessing_summary": preprocessing_summary
        or PreprocessingSummary(
            manifest_path=str(config.manifest_path),
            processed_manifest_path=str(config.processed_manifest_path),
            processed_corpus_path=str(config.processed_corpus_path),
            document_count=len(manifest_documents),
            chunk_count=0,
        ),
        "retrieval_handles": retrieval_handles or {},
        "executive_summary": [],
        "company_strategy_summaries": {},
        "quick_comparison_panel": [],
        "citation_refs": [],
        "charts": [],
        "chart_selection": [],
        "comparability_decisions": [],
        "low_confidence_claims": [],
        "reference_only_rows": [],
        "selected_comparison_rows": [],
        "supervisor_score_rationales": [],
        "supervisor_swot": [],
        "implications": [],
        "limitations": [],
        "review_issues": [],
        "validation_warnings": [],
        "retry_budget": RetryBudget(
            schema_validation_max=config.max_schema_retries,
            review_max=config.max_review_retries,
        ),
        "report_artifacts": [
            ReportArtifact(
                artifact_type="markdown", path=str(config.output_markdown_path)
            ),
            ReportArtifact(artifact_type="html", path=str(config.output_html_path)),
            ReportArtifact(artifact_type="pdf", path=str(config.output_pdf_path)),
            ReportArtifact(artifact_type="log", path=str(config.log_path)),
        ],
        "execution_log": [log_entry],
        "schema_retry_count": 0,
        "review_retry_count": 0,
        "current_step": "supervisor_blueprint",
        "routing_reason": None,
        "status": "initialized",
        "last_error": None,
    }


def append_execution_log(
    state: AgentState,
    *,
    step: WorkflowStep,
    status: WorkflowStatus,
    message: str,
    attempt: int = 0,
) -> list[ExecutionLogEntry]:
    entries = list(state.get("execution_log", []))
    entries.append(
        ExecutionLogEntry(
            timestamp=_utc_now_iso(),
            step=step,
            status=status,
            message=message,
            attempt=attempt,
        )
    )
    return entries


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

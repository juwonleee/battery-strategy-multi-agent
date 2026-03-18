from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, TypedDict

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from config import AppConfig


WorkflowStep = Literal[
    "market_research",
    "lges_analysis",
    "catl_analysis",
    "comparison",
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
    "market_research",
    "lges_analysis",
    "catl_analysis",
    "comparison",
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
    artifact_type: Literal["markdown", "pdf", "json", "log"]
    path: str
    created: bool = False


class MarketContext(BaseModel):
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    comparison_axes: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


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
        "goal": "Compare LGES and CATL diversification strategies",
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
        "citation_refs": [],
        "low_confidence_claims": [],
        "review_issues": [],
        "retry_budget": RetryBudget(
            schema_validation_max=config.max_schema_retries,
            review_max=config.max_review_retries,
        ),
        "report_artifacts": [
            ReportArtifact(
                artifact_type="markdown", path=str(config.output_markdown_path)
            ),
            ReportArtifact(artifact_type="pdf", path=str(config.output_pdf_path)),
            ReportArtifact(artifact_type="log", path=str(config.log_path)),
        ],
        "execution_log": [log_entry],
        "schema_retry_count": 0,
        "review_retry_count": 0,
        "current_step": "market_research",
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

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    company_name: str
    business_overview: str
    core_products: list[str] = Field(default_factory=list)
    diversification_strategy: list[str] = Field(default_factory=list)
    regional_strategy: list[str] = Field(default_factory=list)
    technology_strategy: list[str] = Field(default_factory=list)
    financial_indicators: dict[str, str] = Field(default_factory=dict)
    risk_factors: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    strategy_axis: str
    lges_value: str
    catl_value: str
    difference: str
    implication: str
    evidence_refs: list[str] = Field(default_factory=list)


class SwotEntry(BaseModel):
    company_name: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class Scorecard(BaseModel):
    company_name: str
    diversification_strength: int | None = Field(default=None, ge=1, le=5)
    cost_competitiveness: int | None = Field(default=None, ge=1, le=5)
    market_adaptability: int | None = Field(default=None, ge=1, le=5)
    risk_exposure: int | None = Field(default=None, ge=1, le=5)
    score_rationale: str
    evidence_refs: list[str] = Field(default_factory=list)


class ClaimTrace(BaseModel):
    claim: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence_level: Literal["high", "medium", "low"]


class ReviewResult(BaseModel):
    passed: bool
    revision_target: str | None = None
    review_issues: list[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    goal: str
    target_companies: list[str]
    research_questions: list[str]
    source_documents: list[str]
    market_context: str
    market_context_summary: str
    lges_profile: CompanyProfile
    catl_profile: CompanyProfile
    comparison_matrix: list[ComparisonRow]
    swot_matrix: list[SwotEntry]
    scorecard: list[Scorecard]
    citation_refs: list[str]
    low_confidence_claims: list[ClaimTrace]
    review_result: ReviewResult
    review_issues: list[str]
    schema_retry_count: int
    review_retry_count: int
    current_step: str
    status: str

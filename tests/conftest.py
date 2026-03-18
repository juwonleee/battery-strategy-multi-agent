import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import AppConfig, RuntimePaths
from state import (
    ChartSeries,
    ChartSpec,
    ComparabilityPrecheckRow,
    ComparisonRow,
    CompanyProfile,
    DocumentRef,
    EvidenceRef,
    FinancialIndicator,
    FinalJudgment,
    MarketContext,
    MetricComparisonRow,
    PreprocessingSummary,
    ReportBlueprint,
    ReviewResult,
    ScoreCriterion,
    Scorecard,
    SwotEntry,
    SynthesisClaim,
    WorkerTaskSpec,
    build_initial_state,
)


@pytest.fixture
def test_config(tmp_path: Path) -> AppConfig:
    paths = RuntimePaths.from_root(tmp_path)
    paths.ensure_directories()
    return AppConfig(
        openai_api_key="test-key",
        openai_model="gpt-4.1-mini",
        openai_timeout_seconds=60,
        openai_max_output_tokens=2000,
        embedding_model="intfloat/multilingual-e5-large",
        manifest_path=tmp_path / "data" / "document_manifest.json",
        processed_manifest_path=tmp_path / "data" / "processed" / "document_manifest.processed.json",
        processed_corpus_path=tmp_path / "data" / "processed" / "corpus.jsonl",
        faiss_index_path=tmp_path / "data" / "index" / "faiss.index",
        retrieval_metadata_path=tmp_path / "data" / "index" / "faiss_metadata.jsonl",
        retrieval_manifest_path=tmp_path / "data" / "index" / "retrieval_manifest.json",
        output_markdown_path=tmp_path / "outputs" / "report.md",
        output_html_path=tmp_path / "outputs" / "report.html",
        output_pdf_path=tmp_path / "outputs" / "report.pdf",
        log_path=tmp_path / "logs" / "app.log",
        preprocess_chunk_size=1200,
        preprocess_chunk_overlap=200,
        retrieval_top_k=6,
        max_schema_retries=2,
        max_review_retries=2,
        paths=paths,
    )


@pytest.fixture
def sample_documents() -> list[DocumentRef]:
    return [
        DocumentRef(
            document_id="market-001",
            title="Sample Market Report",
            source_path="data/raw/sample-market.pdf",
            source_type="industry_report",
            company_scope="market",
            published_at="2025-01-01",
            page_range="1-2",
        ),
        DocumentRef(
            document_id="lges-001",
            title="Sample LGES Deck",
            source_path="data/raw/sample-lges.pdf",
            source_type="company_report",
            company_scope="lges",
            published_at="2025-02-01",
            page_range="3-4",
        ),
        DocumentRef(
            document_id="catl-001",
            title="Sample CATL Prospectus",
            source_path="data/raw/sample-catl.pdf",
            source_type="regulatory_filing",
            company_scope="catl",
            published_at="2025-03-01",
            page_range="5-8",
        ),
    ]


@pytest.fixture
def preprocessing_summary(test_config: AppConfig) -> PreprocessingSummary:
    return PreprocessingSummary(
        manifest_path=str(test_config.manifest_path),
        processed_manifest_path=str(test_config.processed_manifest_path),
        processed_corpus_path=str(test_config.processed_corpus_path),
        document_count=3,
        chunk_count=6,
        chunk_files={
            "market-001": str(test_config.paths.processed_dir / "market-001.chunks.json"),
            "lges-001": str(test_config.paths.processed_dir / "lges-001.chunks.json"),
            "catl-001": str(test_config.paths.processed_dir / "catl-001.chunks.json"),
        },
    )


@pytest.fixture
def sample_state(
    test_config: AppConfig,
    sample_documents: list[DocumentRef],
    preprocessing_summary: PreprocessingSummary,
):
    market_ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)
    catl_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p005-c01", page=5)
    comparison_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p006-c02", page=6)

    state = build_initial_state(
        test_config,
        source_documents=sample_documents,
        retrieval_handles={"faiss_index_path": str(test_config.faiss_index_path)},
        preprocessing_summary=preprocessing_summary,
    )
    state.update(
        {
            "market_context": MarketContext(
                summary="Battery supply chains are regionalizing while ESS demand broadens portfolio requirements.",
                key_findings=[
                    "Regional policy is reshaping battery manufacturing footprints.",
                    "ESS demand is emerging as a second growth pillar beyond EV.",
                ],
                comparison_axes=[
                    "Regional expansion",
                    "Portfolio breadth",
                    "Cost competitiveness",
                ],
                evidence_refs=[market_ref],
            ),
            "market_context_summary": "Battery supply chains are regionalizing while ESS demand broadens portfolio requirements.",
            "lges_profile": CompanyProfile(
                company_name="LG Energy Solution",
                business_overview="LGES is broadening its EV battery base with ESS and North American localized production.",
                core_products=["Pouch batteries", "46-series cells", "ESS batteries"],
                diversification_strategy=["Expand ESS", "Localize North American LFP production"],
                regional_strategy=["North America expansion", "Selective customer diversification"],
                technology_strategy=["46-series ramp", "LFP lineup expansion"],
                financial_indicators=[
                    FinancialIndicator(metric="Revenue guidance", value="Mid-teen growth"),
                ],
                risk_factors=["EV slowdown exposure"],
                evidence_refs=[lges_ref],
            ),
            "catl_profile": CompanyProfile(
                company_name="CATL",
                business_overview="CATL is extending scale advantages across EV, ESS, and adjacent battery applications.",
                core_products=["EV batteries", "ESS batteries", "Sodium-ion batteries"],
                diversification_strategy=["Expand ESS", "Develop sodium-ion applications"],
                regional_strategy=["Overseas manufacturing expansion"],
                technology_strategy=["Sodium-ion", "Next-gen chemistry investment"],
                financial_indicators=[
                    FinancialIndicator(metric="Market position", value="Leading global share"),
                ],
                risk_factors=["Pricing pressure", "Policy exposure"],
                evidence_refs=[catl_ref],
            ),
            "comparison_matrix": [
                ComparisonRow(
                    strategy_axis="Portfolio breadth",
                    lges_value="ESS and localized EV expansion",
                    catl_value="ESS, sodium-ion, and ecosystem expansion",
                    difference="CATL is broader across adjacent applications",
                    implication="CATL may have broader optionality while LGES remains more focused.",
                    evidence_refs=[comparison_ref],
                )
            ],
            "synthesis_claims": [
                SynthesisClaim(
                    scope="catl",
                    category="portfolio_breadth",
                    ordinal=1,
                    claim_text="CATL may have broader optionality while LGES remains more focused.",
                    supporting_claim_ids=["market-policy_signal-1", "catl-diversification_strategy-1"],
                )
            ],
            "score_criteria": [
                ScoreCriterion(
                    criterion_key="diversification_strength",
                    company_scope="lges",
                    score=3,
                    rationale="LGES is diversifying through ESS and regional localization.",
                    supporting_claim_ids=["lges-diversification_strategy-1", "market-comparison_axis-1"],
                    evidence_refs=[lges_ref],
                ),
                ScoreCriterion(
                    criterion_key="diversification_strength",
                    company_scope="catl",
                    score=5,
                    rationale="CATL combines scale, chemistry breadth, and ESS exposure.",
                    supporting_claim_ids=["catl-diversification_strategy-1", "market-comparison_axis-1"],
                    evidence_refs=[catl_ref],
                ),
            ],
            "final_judgment": FinalJudgment(
                judgment_text="CATL has broader diversification optionality, while LGES is more regionally focused.",
                supporting_claim_ids=["market-policy_signal-1", "catl-diversification_strategy-1"],
            ),
            "report_blueprint": ReportBlueprint(
                comparison_axes=[
                    "portfolio_diversification",
                    "technology_product_strategy",
                    "regional_supply_chain",
                    "financial_resilience",
                ],
                comparability_precheck=[
                    ComparabilityPrecheckRow(
                        metric_name="operating_margin",
                        company_scope="lges",
                        period="FY2025",
                        status="reference_only",
                        reason="LGES operating margin은 CATL 공시 기준과 다르다.",
                    ),
                    ComparabilityPrecheckRow(
                        metric_name="net_profit_margin",
                        company_scope="catl",
                        period="FY2024",
                        status="reference_only",
                        reason="CATL net profit margin은 LGES 공시 기준과 직접 정렬되지 않는다.",
                    ),
                    ComparabilityPrecheckRow(
                        metric_name="portfolio_breadth",
                        company_scope="shared",
                        period="reported",
                        status="direct",
                        reason="포트폴리오 다각화 방향은 직접 비교 가능한 전략 축이다.",
                    ),
                ],
                worker_task_specs=[
                    WorkerTaskSpec(
                        worker_id="market_research",
                        question_set=["시장 배경과 비교 축을 추출하라."],
                        required_output_fields=["atomic_claims", "metric_claims", "source_evidence_refs"],
                        forbidden_outputs=["final_judgment", "executive_summary", "final_swot", "final_score_rationale"],
                    ),
                    WorkerTaskSpec(
                        worker_id="lges_analysis",
                        question_set=["LGES 근거를 추출하라."],
                        required_output_fields=["atomic_claims", "metric_claims", "source_evidence_refs"],
                        forbidden_outputs=["final_judgment", "executive_summary", "final_swot", "final_score_rationale"],
                    ),
                    WorkerTaskSpec(
                        worker_id="catl_analysis",
                        question_set=["CATL 근거를 추출하라."],
                        required_output_fields=["atomic_claims", "metric_claims", "source_evidence_refs"],
                        forbidden_outputs=["final_judgment", "executive_summary", "final_swot", "final_score_rationale"],
                    ),
                ],
            ),
            "metric_comparison_rows": [
                MetricComparisonRow(
                    row_id="profitability_lges",
                    row_group="profitability_reported",
                    metric_name="operating_margin",
                    period="FY2025",
                    lges_value="7.2%",
                    catl_value=None,
                    basis_note="Reported basis differs across companies and is preserved as disclosed.",
                    comparability_status="reference_only",
                    interpretation="LGES 공시 기준으로만 제공되어 reference-only로 해석한다.",
                    evidence_refs=[lges_ref],
                ),
                MetricComparisonRow(
                    row_id="profitability_catl",
                    row_group="profitability_reported",
                    metric_name="net_profit_margin",
                    period="FY2024",
                    lges_value=None,
                    catl_value="11%",
                    basis_note="Reported basis differs across companies and is preserved as disclosed.",
                    comparability_status="reference_only",
                    interpretation="CATL 공시 기준으로만 제공되어 reference-only로 해석한다.",
                    evidence_refs=[catl_ref],
                ),
            ],
            "charts": [
                ChartSpec(
                    chart_id="revenue_comparison",
                    title="Revenue Comparison",
                    series=[
                        ChartSeries(
                            label="LGES Revenue",
                            values=[None],
                            source_row_ids=["lges-revenue-growth-guidance-1"],
                        ),
                        ChartSeries(
                            label="CATL Revenue",
                            values=[400.0],
                            source_row_ids=["catl-revenue-1"],
                        ),
                    ],
                    x_axis_periods=["FY2025"],
                    y_axis_label="Revenue (reported units)",
                    interpretation="단일 시점 reported revenue 비교 패널이다.",
                    caution_note="추세가 아니라 snapshot 비교다.",
                ),
            ],
            "selected_comparison_rows": [
                MetricComparisonRow(
                    row_id="portfolio_breadth",
                    row_group="direct_comparison",
                    metric_name="portfolio_breadth",
                    period="reported",
                    lges_value="ESS and localized EV expansion",
                    catl_value="ESS, sodium-ion, and ecosystem expansion",
                    basis_note="Direct strategic comparison axis.",
                    comparability_status="direct",
                    interpretation="양사의 포트폴리오 폭을 직접 비교한 supervisor-selected row.",
                    evidence_refs=[comparison_ref],
                )
            ],
            "reference_only_rows": [
                MetricComparisonRow(
                    row_id="profitability_lges",
                    row_group="profitability_reported",
                    metric_name="operating_margin",
                    period="FY2025",
                    lges_value="7.2%",
                    catl_value=None,
                    basis_note="Reported basis differs across companies and is preserved as disclosed.",
                    comparability_status="reference_only",
                    interpretation="LGES 공시 기준으로만 제공되어 reference-only로 해석한다.",
                    evidence_refs=[lges_ref],
                ),
                MetricComparisonRow(
                    row_id="profitability_catl",
                    row_group="profitability_reported",
                    metric_name="net_profit_margin",
                    period="FY2024",
                    lges_value=None,
                    catl_value="11%",
                    basis_note="Reported basis differs across companies and is preserved as disclosed.",
                    comparability_status="reference_only",
                    interpretation="CATL 공시 기준으로만 제공되어 reference-only로 해석한다.",
                    evidence_refs=[catl_ref],
                ),
            ],
            "chart_selection": [
                ChartSpec(
                    chart_id="revenue_comparison",
                    title="Revenue Comparison",
                    series=[
                        ChartSeries(
                            label="LGES Revenue",
                            values=[None],
                            source_row_ids=["lges-revenue-growth-guidance-1"],
                        ),
                        ChartSeries(
                            label="CATL Revenue",
                            values=[400.0],
                            source_row_ids=["catl-revenue-1"],
                        ),
                    ],
                    x_axis_periods=["FY2025"],
                    y_axis_label="Revenue (reported units)",
                    interpretation="단일 시점 reported revenue 비교 패널이다.",
                    caution_note="추세가 아니라 snapshot 비교다.",
                )
            ],
            "quick_comparison_panel": [
                ComparisonRow(
                    strategy_axis="Portfolio Diversification",
                    lges_value="ESS and localized EV expansion",
                    catl_value="ESS, sodium-ion, and ecosystem expansion",
                    difference="CATL is broader across adjacent applications",
                    implication="CATL may have broader optionality while LGES remains more focused.",
                    evidence_refs=[comparison_ref],
                )
            ],
            "company_strategy_summaries": {
                "lges": [
                    "포트폴리오: Expand ESS",
                    "기술/제품: 46-series ramp",
                    "지역/공급망: North America expansion",
                    "리스크: EV slowdown exposure",
                ],
                "catl": [
                    "포트폴리오: Expand ESS",
                    "기술/제품: Sodium-ion",
                    "지역/공급망: Overseas manufacturing expansion",
                    "리스크: Pricing pressure",
                ],
            },
            "executive_summary": [
                "목적: LGES와 CATL의 다각화 전략을 비교 분석한다",
                "CATL has broader diversification optionality, while LGES is more regionally focused.",
                "CATL may have broader optionality while LGES remains more focused.",
                "일부 수익성 지표는 공시 기준 차이로 reference-only로 처리했다.",
            ],
            "supervisor_swot": [
                SwotEntry(
                    company_name="LG Energy Solution",
                    strengths=["ESS와 북미 현지화 확장은 EV 외 포트폴리오 전환 옵션을 만든다."],
                    weaknesses=["EV 수요 민감도는 단기 실적 변동성을 키울 수 있다."],
                    opportunities=["ESS demand growth 환경은 LGES의 확장 기회로 읽힌다."],
                    threats=["직접 비교가 어려운 수익성 지표는 보수적으로 해석해야 한다."],
                    evidence_refs=[lges_ref],
                ),
                SwotEntry(
                    company_name="CATL",
                    strengths=["규모와 chemistry breadth는 현재 체급과 선택지 폭을 동시에 강화한다."],
                    weaknesses=["Broader operational complexity는 실행 부담으로 연결될 수 있다."],
                    opportunities=["Sodium-ion commercialization은 추가 성장 기회가 된다."],
                    threats=["Policy and trade constraints"],
                    evidence_refs=[catl_ref],
                ),
            ],
            "swot_matrix": [
                SwotEntry(
                    company_name="LG Energy Solution",
                    strengths=["ESS와 북미 현지화 확장은 EV 외 포트폴리오 전환 옵션을 만든다."],
                    weaknesses=["EV 수요 민감도는 단기 실적 변동성을 키울 수 있다."],
                    opportunities=["ESS demand growth 환경은 LGES의 확장 기회로 읽힌다."],
                    threats=["직접 비교가 어려운 수익성 지표는 보수적으로 해석해야 한다."],
                    evidence_refs=[lges_ref],
                ),
                SwotEntry(
                    company_name="CATL",
                    strengths=["규모와 chemistry breadth는 현재 체급과 선택지 폭을 동시에 강화한다."],
                    weaknesses=["Broader operational complexity는 실행 부담으로 연결될 수 있다."],
                    opportunities=["Sodium-ion commercialization은 추가 성장 기회가 된다."],
                    threats=["Policy and trade constraints"],
                    evidence_refs=[catl_ref],
                ),
            ],
            "supervisor_score_rationales": [
                ScoreCriterion(
                    criterion_key="diversification_strength",
                    company_scope="lges",
                    score=3,
                    rationale="포트폴리오 다각화 폭 기준에서 포트폴리오: Expand ESS를 중심으로 판단했다.",
                    supporting_claim_ids=["lges-diversification_strategy-1", "market-comparison_axis-1"],
                    evidence_refs=[lges_ref],
                ),
                ScoreCriterion(
                    criterion_key="diversification_strength",
                    company_scope="catl",
                    score=5,
                    rationale="포트폴리오 다각화 폭 기준에서 포트폴리오: Expand ESS를 중심으로 판단했다.",
                    supporting_claim_ids=["catl-diversification_strategy-1", "market-comparison_axis-1"],
                    evidence_refs=[catl_ref],
                ),
            ],
            "scorecard": [
                Scorecard(
                    company_name="LG Energy Solution",
                    diversification_strength=3,
                    cost_competitiveness=3,
                    market_adaptability=4,
                    risk_exposure=3,
                    score_rationale="LGES는 ESS와 지역 전환 옵션을 보유하지만 EV 회복 의존도가 남아 있다.",
                    evidence_refs=[lges_ref],
                ),
                Scorecard(
                    company_name="CATL",
                    diversification_strength=5,
                    cost_competitiveness=5,
                    market_adaptability=4,
                    risk_exposure=3,
                    score_rationale="CATL은 체급과 포트폴리오 폭이 크지만 운영 복잡도 부담이 존재한다.",
                    evidence_refs=[catl_ref],
                ),
            ],
            "implications": [
                "CATL의 포트폴리오 폭은 현재 선택지 우위로 이어진다.",
                "LGES는 지역 전환 옵션 측면의 해석이 중요하다.",
            ],
            "limitations": [
                "일부 수익성 지표는 공시 기준 차이로 직접 비교하지 않고 reference-only로 처리했다."
            ],
            "citation_refs": [market_ref, lges_ref, catl_ref, comparison_ref],
            "low_confidence_claims": [],
            "review_result": ReviewResult(passed=True, revision_target=None, review_issues=[]),
            "review_issues": [],
            "validation_warnings": [],
            "current_step": "finish",
            "status": "completed",
            "routing_reason": "Synthetic completed state for testing.",
            "last_error": None,
        }
    )
    return state

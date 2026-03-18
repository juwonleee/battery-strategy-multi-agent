import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import AppConfig, RuntimePaths
from state import (
    ComparisonRow,
    CompanyProfile,
    DocumentRef,
    EvidenceRef,
    FinancialIndicator,
    MarketContext,
    PreprocessingSummary,
    ReviewResult,
    Scorecard,
    SwotEntry,
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
            "swot_matrix": [
                SwotEntry(
                    company_name="LG Energy Solution",
                    strengths=["Localized North American expansion"],
                    weaknesses=["Higher EV demand sensitivity"],
                    opportunities=["ESS demand growth"],
                    threats=["Pricing competition"],
                    evidence_refs=[lges_ref],
                ),
                SwotEntry(
                    company_name="CATL",
                    strengths=["Scale and chemistry breadth"],
                    weaknesses=["Broader operational complexity"],
                    opportunities=["Sodium-ion commercialization"],
                    threats=["Policy and trade constraints"],
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
                    score_rationale="LGES is diversifying through ESS and regional localization but remains tied to EV recovery.",
                    evidence_refs=[lges_ref],
                ),
                Scorecard(
                    company_name="CATL",
                    diversification_strength=5,
                    cost_competitiveness=5,
                    market_adaptability=4,
                    risk_exposure=3,
                    score_rationale="CATL combines scale, chemistry breadth, and ESS exposure, though this raises execution complexity.",
                    evidence_refs=[catl_ref],
                ),
            ],
            "citation_refs": [market_ref, lges_ref, catl_ref, comparison_ref],
            "low_confidence_claims": [],
            "review_result": ReviewResult(passed=True, revision_target=None, review_issues=[]),
            "review_issues": [],
            "current_step": "finish",
            "status": "completed",
            "routing_reason": "Synthetic completed state for testing.",
            "last_error": None,
        }
    )
    return state

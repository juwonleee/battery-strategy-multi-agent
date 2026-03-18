import pytest
from pydantic import ValidationError

from state import (
    AtomicFactClaim,
    ChartSeries,
    ChartSpec,
    DocumentRef,
    EvidenceRef,
    FinalJudgment,
    MetricComparisonRow,
    MetricFactClaim,
    ReportSpec,
    ScoreCriterion,
    SynthesisClaim,
    build_claim_id,
)


def test_report_spec_accepts_commit1_schema_contract():
    market_ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)
    catl_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p005-c01", page=5)

    market_claim = AtomicFactClaim(
        scope="market",
        category="policy_trend",
        ordinal=1,
        claim_text="Regional subsidy policy is accelerating local battery production.",
        evidence_refs=[market_ref],
    )
    lges_metric = MetricFactClaim(
        scope="lges",
        category="revenue_growth_guidance",
        ordinal=1,
        claim_text="LGES guides to mid-teen revenue growth.",
        metric_name="revenue_growth_guidance",
        value="mid-teen",
        period="FY2025",
        evidence_refs=[lges_ref],
    )
    synthesis = SynthesisClaim(
        scope="catl",
        category="portfolio_optionality",
        ordinal=1,
        claim_text="CATL has broader adjacent portfolio optionality than LGES.",
        supporting_claim_ids=[market_claim.claim_id, lges_metric.claim_id],
        confidence_level="high",
    )
    score = ScoreCriterion(
        criterion_key="diversification_strength",
        company_scope="lges",
        score=4,
        rationale="Localized expansion and ESS exposure provide diversification support.",
        supporting_claim_ids=[lges_metric.claim_id],
        evidence_refs=[lges_ref],
    )
    comparison_row = MetricComparisonRow(
        row_id="profitability_reported",
        row_group="profitability_reported",
        metric_name="operating_margin",
        lges_value="7.2%",
        catl_value="n/a",
        basis_note="Reported values are kept on each company's disclosed basis.",
        evidence_refs=[lges_ref, catl_ref],
    )
    chart = ChartSpec(
        chart_id="revenue_trend",
        title="Revenue Trend",
        series=[
            ChartSeries(label="LGES", values=[1.0], source_row_ids=[comparison_row.row_id]),
        ],
        x_axis_periods=["FY2025"],
        y_axis_label="KRW tn",
    )
    report = ReportSpec(
        title="Battery Strategy Comparison Report",
        atomic_claims=[market_claim],
        metric_claims=[lges_metric],
        synthesis_claims=[synthesis],
        score_criteria=[score],
        metric_comparison_rows=[comparison_row],
        charts=[chart],
        final_judgment=FinalJudgment(
            judgment_text="CATL has broader diversification optionality, while LGES is more regionally focused.",
            supporting_claim_ids=[market_claim.claim_id, lges_metric.claim_id],
        ),
        references=[
            DocumentRef(
                document_id="market-001",
                title="Sample Market Report",
                source_path="data/raw/sample-market.pdf",
            )
        ],
    )

    assert market_claim.claim_id == "market-policy_trend-1"
    assert lges_metric.claim_id == "lges-revenue_growth_guidance-1"
    assert synthesis.claim_id == "catl-portfolio_optionality-1"
    assert report.final_judgment is not None
    assert report.charts[0].series[0].source_row_ids == ["profitability_reported"]


def test_report_spec_rejects_duplicate_claim_ids():
    evidence_ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)

    with pytest.raises(ValidationError, match="claim_id values must be unique"):
        ReportSpec(
            title="Battery Strategy Comparison Report",
            atomic_claims=[
                AtomicFactClaim(
                    scope="market",
                    category="demand_outlook",
                    ordinal=1,
                    claim_text="Demand outlook remains mixed across regions.",
                    evidence_refs=[evidence_ref],
                )
            ],
            metric_claims=[
                MetricFactClaim(
                    scope="market",
                    category="demand_outlook",
                    ordinal=1,
                    claim_text="A duplicate claim id should be rejected.",
                    metric_name="demand_outlook",
                    value="mixed",
                    evidence_refs=[evidence_ref],
                )
            ],
        )

    generated_ids = {
        build_claim_id("market", "demand_outlook", 1),
        build_claim_id("market", "demand_outlook", 2),
        build_claim_id("lges", "demand_outlook", 1),
    }

    assert len(generated_ids) == 3


@pytest.mark.parametrize(
    "payload",
    [
        {
            "criterion_key": "diversification_strength",
            "company_scope": "lges",
            "score": 4,
            "rationale": "Evidence must be materialized on the criterion.",
            "supporting_claim_ids": ["lges-diversification_strength-1"],
        },
        {
            "criterion_key": "diversification_strength",
            "company_scope": "catl",
            "score": 5,
            "rationale": "Empty evidence refs are not allowed.",
            "supporting_claim_ids": ["catl-diversification_strength-1"],
            "evidence_refs": [],
        },
    ],
)
def test_score_criterion_requires_evidence_refs(payload):
    with pytest.raises(ValidationError):
        ScoreCriterion(**payload)

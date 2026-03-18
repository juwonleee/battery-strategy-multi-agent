from copy import deepcopy

from state import (
    AtomicFactClaim,
    CATLFactExtractionOutput,
    ComparisonInputSpec,
    DocumentRef,
    EvidenceRef,
    FinalJudgment,
    LGESFactExtractionOutput,
    MarketFactExtractionOutput,
    MetricComparisonRow,
    MetricFactClaim,
    ScoreCriterion,
    StructuredComparisonOutput,
    SwotEntry,
)
from tools.comparison_contract import (
    build_comparison_input_spec,
    validate_structured_comparison_output,
)


def test_build_comparison_input_spec_caps_claims_per_company_at_twelve(sample_state):
    state = _state_with_first_pass_claims(sample_state)

    input_spec = build_comparison_input_spec(state)

    assert isinstance(input_spec, ComparisonInputSpec)
    assert len(input_spec.lges_catalog.claims) == 12
    assert len(input_spec.catl_catalog.claims) == 12


def test_structured_comparison_output_supporting_claim_ids_must_reference_first_pass_claims(
    sample_state,
):
    state = _state_with_first_pass_claims(sample_state)
    input_spec = build_comparison_input_spec(state)
    valid_claim_ids = sorted(input_spec.allowed_claim_ids())

    output = StructuredComparisonOutput(
        synthesis_claims=[
            {
                "scope": "lges",
                "category": "portfolio_comparison",
                "ordinal": 1,
                "claim_text": "CATL의 포트폴리오 선택지가 더 넓다.",
                "supporting_claim_ids": [valid_claim_ids[0], "unknown-claim-id"],
            }
        ],
        score_criteria=[
            ScoreCriterion(
                criterion_key="diversification_strength",
                company_scope="lges",
                score=4,
                rationale="근거 기반 점수다.",
                supporting_claim_ids=[valid_claim_ids[0]],
                evidence_refs=[_ref("lges-001", "lges-001-p003-c01", 3)],
            )
        ],
        swot_matrix=_swot_entries(),
        final_judgment=FinalJudgment(
            judgment_text="CATL이 더 넓은 선택지를 보유한다.",
            supporting_claim_ids=[valid_claim_ids[0], valid_claim_ids[1]],
        ),
        metric_comparison_rows=[_comparison_row()],
    )

    error = validate_structured_comparison_output(output, input_spec)

    assert error is not None
    assert "unknown supporting_claim_ids" in error


def test_structured_comparison_output_fails_without_supporting_claim_ids(sample_state):
    state = _state_with_first_pass_claims(sample_state)
    input_spec = build_comparison_input_spec(state)
    valid_claim_ids = sorted(input_spec.allowed_claim_ids())

    output = StructuredComparisonOutput(
        synthesis_claims=[
            {
                "scope": "catl",
                "category": "cost_comparison",
                "ordinal": 1,
                "claim_text": "CATL의 원가 경쟁력이 높다.",
                "supporting_claim_ids": [],
            }
        ],
        score_criteria=[
            ScoreCriterion(
                criterion_key="cost_competitiveness",
                company_scope="catl",
                score=5,
                rationale="근거 기반 점수다.",
                supporting_claim_ids=[valid_claim_ids[0]],
                evidence_refs=[_ref("catl-001", "catl-001-p005-c01", 5)],
            )
        ],
        swot_matrix=_swot_entries(),
        final_judgment=FinalJudgment(
            judgment_text="CATL의 규모 우위가 크다.",
            supporting_claim_ids=[valid_claim_ids[0], valid_claim_ids[1]],
        ),
        metric_comparison_rows=[_comparison_row()],
    )

    error = validate_structured_comparison_output(output, input_spec)

    assert error is not None
    assert "without supporting_claim_ids" in error


def _state_with_first_pass_claims(sample_state):
    state = deepcopy(sample_state)
    market_ref = _ref("market-001", "market-001-p001-c01", 1)
    lges_ref = _ref("lges-001", "lges-001-p003-c01", 3)
    catl_ref = _ref("catl-001", "catl-001-p005-c01", 5)

    state["document_manifest"] = [
        DocumentRef(
            document_id="market-001",
            title="Sample Market Report",
            source_path="data/raw/sample-market.pdf",
            company_scope="market",
        ),
        DocumentRef(
            document_id="lges-001",
            title="Sample LGES Deck",
            source_path="data/raw/sample-lges.pdf",
            company_scope="lges",
        ),
        DocumentRef(
            document_id="catl-001",
            title="Sample CATL Prospectus",
            source_path="data/raw/sample-catl.pdf",
            company_scope="catl",
        ),
    ]
    state["market_facts"] = MarketFactExtractionOutput(
        scope="market",
        summary="시장 배경 요약",
        atomic_claims=[
            _atomic_claim("market", "market_overview", 1, "시장 성장성은 둔화되고 있다.", market_ref),
            _atomic_claim("market", "comparison_axis", 2, "지역 생산 대응력", market_ref),
            _atomic_claim("market", "policy_signal", 3, "정책 지역화 압력이 커지고 있다.", market_ref),
        ],
        metric_claims=[],
        source_evidence_refs=[market_ref],
    )
    state["lges_facts"] = LGESFactExtractionOutput(
        scope="lges",
        summary="LGES 요약",
        atomic_claims=[
            _atomic_claim("lges", "diversification_strategy", 1, "ESS 확대를 추진한다.", lges_ref),
            _atomic_claim("lges", "regional_strategy", 2, "북미 현지화에 집중한다.", lges_ref),
            _atomic_claim("lges", "technology_strategy", 3, "46-series 양산을 준비한다.", lges_ref),
            _atomic_claim("lges", "risk_factor", 4, "EV 수요 민감도가 높다.", lges_ref),
            _atomic_claim("lges", "core_product", 5, "파우치형 배터리를 공급한다.", lges_ref),
        ],
        metric_claims=[
            _metric_claim("lges", "revenue_growth_guidance", 1, "Revenue growth guidance", "mid-teen", lges_ref),
            _metric_claim("lges", "operating_margin_guidance_or_actual", 2, "Operating margin", "7.2%", lges_ref),
            _metric_claim("lges", "capex", 3, "Capex", "KRW 10tn", lges_ref),
            _metric_claim("lges", "ess_capacity", 4, "ESS capacity", "15GWh", lges_ref),
            _metric_claim("lges", "secured_order_volume", 5, "Secured order volume", "100GWh", lges_ref),
            _metric_claim("lges", "revenue_growth_guidance", 6, "Revenue growth guidance backup", "high-teen", lges_ref),
        ],
        source_evidence_refs=[lges_ref],
    )
    state["catl_facts"] = CATLFactExtractionOutput(
        scope="catl",
        summary="CATL 요약",
        atomic_claims=[
            _atomic_claim("catl", "diversification_strategy", 1, "ESS와 생태계 확장을 병행한다.", catl_ref),
            _atomic_claim("catl", "regional_strategy", 2, "해외 생산거점을 확장한다.", catl_ref),
            _atomic_claim("catl", "technology_strategy", 3, "차세대 화학계 투자에 집중한다.", catl_ref),
            _atomic_claim("catl", "risk_factor", 4, "정책과 가격 압력을 동시에 받는다.", catl_ref),
            _atomic_claim("catl", "core_product", 5, "EV와 ESS 배터리를 공급한다.", catl_ref),
        ],
        metric_claims=[
            _metric_claim("catl", "revenue", 1, "Revenue", "CNY 400bn", catl_ref),
            _metric_claim("catl", "gross_profit_margin", 2, "Gross profit margin", "23%", catl_ref),
            _metric_claim("catl", "net_profit_margin", 3, "Net profit margin", "11%", catl_ref),
            _metric_claim("catl", "profit_for_the_year", 4, "Profit for the year", "CNY 44bn", catl_ref),
            _metric_claim("catl", "roe", 5, "ROE", "19%", catl_ref),
            _metric_claim("catl", "operating_cash_flow", 6, "Operating cash flow", "CNY 80bn", catl_ref),
        ],
        source_evidence_refs=[catl_ref],
    )
    return state


def _atomic_claim(scope, category, ordinal, claim_text, evidence_ref):
    return AtomicFactClaim(
        scope=scope,
        category=category,
        ordinal=ordinal,
        claim_text=claim_text,
        evidence_refs=[evidence_ref],
    )


def _metric_claim(scope, category, ordinal, metric_name, value, evidence_ref):
    return MetricFactClaim(
        scope=scope,
        category=category,
        ordinal=ordinal,
        claim_text=f"{metric_name}: {value}",
        metric_name=metric_name,
        value=value,
        evidence_refs=[evidence_ref],
    )


def _comparison_row():
    ref = _ref("market-001", "market-001-p001-c01", 1)
    return MetricComparisonRow(
        row_id="portfolio_breadth",
        row_group="company_comparison",
        metric_name="portfolio_breadth",
        lges_value="집중형",
        catl_value="확장형",
        basis_note="claim catalog 기준 비교",
        evidence_refs=[ref],
    )


def _swot_entries():
    lges_ref = _ref("lges-001", "lges-001-p003-c01", 3)
    catl_ref = _ref("catl-001", "catl-001-p005-c01", 5)
    return [
        SwotEntry(
            company_name="LG Energy Solution",
            strengths=["북미 현지화"],
            weaknesses=["EV 민감도"],
            opportunities=["ESS 성장"],
            threats=["가격 경쟁"],
            evidence_refs=[lges_ref],
        ),
        SwotEntry(
            company_name="CATL",
            strengths=["규모 우위"],
            weaknesses=["운영 복잡성"],
            opportunities=["생태계 확장"],
            threats=["정책 압력"],
            evidence_refs=[catl_ref],
        ),
    ]


def _ref(document_id, chunk_id, page):
    return EvidenceRef(document_id=document_id, chunk_id=chunk_id, page=page)

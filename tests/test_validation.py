from copy import deepcopy

from agents.comparison import comparison_agent
from agents.review import review_agent
from state import (
    AtomicFactClaim,
    CompanyClaimCatalog,
    ComparisonInputClaim,
    ComparisonInputSpec,
    EvidenceRef,
    FinalJudgment,
    MarketFactExtractionOutput,
    MetricComparisonRow,
    ScoreCriterion,
    StructuredComparisonOutput,
    SwotEntry,
    SynthesisClaim,
)
from tools.validation import (
    validate_comparison_outputs,
    validate_fact_extraction_output,
    validate_final_delivery_state,
)


def test_validate_fact_extraction_output_fails_when_fact_claim_evidence_is_missing():
    ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)
    invalid_claim = AtomicFactClaim.model_construct(
        scope="market",
        category="market_overview",
        ordinal=1,
        claim_id="market-market_overview-1",
        claim_text="근거 없는 주장",
        evidence_refs=[],
    )
    output = MarketFactExtractionOutput.model_construct(
        scope="market",
        summary="시장 요약",
        atomic_claims=[invalid_claim],
        metric_claims=[],
        source_evidence_refs=[ref],
    )

    result = validate_fact_extraction_output("market", output)

    assert result.hard_errors
    assert result.hard_errors[0].startswith("[hard-gate:fact-claim-evidence]")


def test_validate_comparison_outputs_fails_for_insufficient_support_and_missing_score_evidence(
    sample_state,
):
    state = deepcopy(sample_state)
    state["comparison_input_spec"] = _comparison_input_spec()
    invalid_score = ScoreCriterion.model_construct(
        criterion_key="cost_competitiveness",
        company_scope="catl",
        score=5,
        rationale="근거 누락 점수",
        supporting_claim_ids=["lges-capex-1"],
        evidence_refs=[],
    )
    output = StructuredComparisonOutput(
        synthesis_claims=[
            SynthesisClaim(
                scope="catl",
                category="cost_position",
                ordinal=1,
                claim_text="CATL의 원가 경쟁력이 더 높다.",
                supporting_claim_ids=["lges-capex-1"],
            )
        ],
        score_criteria=[invalid_score],
        swot_matrix=_swot_entries(),
        final_judgment=FinalJudgment(
            judgment_text="CATL이 상대적으로 우위다.",
            supporting_claim_ids=["lges-capex-1", "catl-revenue-1"],
        ),
        metric_comparison_rows=[_metric_row()],
    )

    result = validate_comparison_outputs(state, output)

    assert any("synthesis-support-count" in error for error in result.hard_errors)
    assert any("score-criterion-evidence" in error for error in result.hard_errors)


def test_validate_final_delivery_state_fails_when_required_section_is_missing(sample_state):
    state = deepcopy(sample_state)
    state["final_judgment"] = None

    result = validate_final_delivery_state(state)

    assert any("required-section-missing" in error for error in result.hard_errors)


def test_validate_final_delivery_state_blocks_fallback_ref_backfill(sample_state):
    state = deepcopy(sample_state)
    state["score_criteria"] = []

    result = validate_final_delivery_state(state)

    assert any("no-fallback-ref-backfill" in error for error in result.hard_errors)


def test_validate_final_delivery_state_requires_required_chart_ids(sample_state):
    state = deepcopy(sample_state)
    state["charts"] = []

    result = validate_final_delivery_state(state)

    assert any("required-chart-missing" in error for error in result.hard_errors)


def test_validate_final_delivery_state_emits_soft_warnings_only(sample_state):
    state = deepcopy(sample_state)
    state["market_context"].summary = state["final_judgment"].judgment_text
    state["metric_comparison_rows"][0].basis_note = ""

    result = validate_final_delivery_state(state)

    assert result.hard_errors == []
    assert any("Summary text exactly duplicates" in warning for warning in result.soft_warnings)
    assert any("basis mismatch note" in warning for warning in result.soft_warnings)


def test_comparison_agent_surfaces_hard_gate_failure(monkeypatch, sample_state):
    valid_input_spec = _comparison_input_spec()
    comparison_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p006-c02", page=6)

    monkeypatch.setattr(
        "agents.comparison.build_comparison_input_spec",
        lambda _state: valid_input_spec,
    )
    monkeypatch.setattr("agents.comparison.build_chart_specs", lambda **_kwargs: ["stub"])
    monkeypatch.setattr("agents.comparison.missing_required_chart_ids", lambda _charts: [])
    monkeypatch.setattr(
        "agents.comparison.invoke_structured_output",
        lambda **_kwargs: StructuredComparisonOutput(
            synthesis_claims=[
                SynthesisClaim(
                    scope="catl",
                    category="portfolio_advantage",
                    ordinal=1,
                    claim_text="CATL의 포트폴리오 선택지가 더 넓다.",
                    supporting_claim_ids=["catl-revenue-1"],
                )
            ],
            score_criteria=[
                ScoreCriterion(
                    criterion_key="diversification_strength",
                    company_scope="catl",
                    score=5,
                    rationale="정량 근거 기반 점수다.",
                    supporting_claim_ids=["catl-revenue-1"],
                    evidence_refs=[comparison_ref],
                )
            ],
            swot_matrix=_swot_entries(),
            final_judgment=FinalJudgment(
                judgment_text="CATL이 더 넓은 선택지를 보유한다.",
                supporting_claim_ids=["lges-capex-1", "catl-revenue-1"],
            ),
            metric_comparison_rows=[_metric_row()],
        ),
    )

    result = comparison_agent(sample_state)

    assert result["status"] == "failed"
    assert result["last_error"].startswith("[hard-gate:synthesis-support-count]")


def test_review_agent_fails_when_final_hard_gate_fails(monkeypatch, sample_state):
    state = deepcopy(sample_state)
    state["final_judgment"] = None

    monkeypatch.setattr(
        "agents.review.invoke_structured_output",
        lambda **_kwargs: {"passed": True, "revision_target": None, "review_issues": []},
    )

    result = review_agent(state)

    assert result["status"] == "failed"
    assert "final_judgment" in result["last_error"]


def test_review_agent_preserves_soft_warnings_when_review_passes(monkeypatch, sample_state):
    state = deepcopy(sample_state)
    state["market_context"].summary = state["final_judgment"].judgment_text

    monkeypatch.setattr(
        "agents.review.invoke_structured_output",
        lambda **_kwargs: {"passed": True, "revision_target": None, "review_issues": []},
    )

    result = review_agent(state)

    assert result["status"] == "reviewed"
    assert result["report_spec"].title == "배터리 전략 비교 보고서"
    assert any(
        "Summary text exactly duplicates" in warning
        for warning in result["validation_warnings"]
    )


def test_review_agent_passes_report_spec_to_prompt(monkeypatch, sample_state):
    captured = {}

    def fake_build_review_prompt(**kwargs):
        captured.update(kwargs)
        from prompts import PromptBundle

        return PromptBundle(name="review", instructions="test", input_text="{}")

    monkeypatch.setattr("agents.review.build_review_prompt", fake_build_review_prompt)
    monkeypatch.setattr(
        "agents.review.invoke_structured_output",
        lambda **_kwargs: {"passed": True, "revision_target": None, "review_issues": []},
    )

    result = review_agent(sample_state)

    assert result["status"] == "reviewed"
    assert captured["report_spec"].title == "배터리 전략 비교 보고서"
    assert captured["validation_warnings"] == []


def _comparison_input_spec() -> ComparisonInputSpec:
    return ComparisonInputSpec(
        lges_catalog=CompanyClaimCatalog(
            owner_scope="lges",
            claims=[
                ComparisonInputClaim(
                    claim_id="lges-capex-1",
                    scope="lges",
                    category="capex",
                    claim_text="LGES는 CAPEX를 유지한다.",
                    key_value="KRW 10tn",
                    source_label="Sample LGES Deck",
                    page_locator="p.3",
                )
            ],
        ),
        catl_catalog=CompanyClaimCatalog(
            owner_scope="catl",
            claims=[
                ComparisonInputClaim(
                    claim_id="catl-revenue-1",
                    scope="catl",
                    category="revenue",
                    claim_text="CATL revenue remains strong.",
                    key_value="CNY 400bn",
                    source_label="Sample CATL Prospectus",
                    page_locator="p.5",
                )
            ],
        ),
    )


def _metric_row() -> MetricComparisonRow:
    ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p006-c02", page=6)
    return MetricComparisonRow(
        row_id="portfolio_breadth",
        row_group="company_comparison",
        metric_name="portfolio_breadth",
        lges_value="ESS and localized EV expansion",
        catl_value="ESS, sodium-ion, and ecosystem expansion",
        basis_note="근거 기반 비교",
        evidence_refs=[ref],
    )


def _swot_entries() -> list[SwotEntry]:
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)
    catl_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p005-c01", page=5)
    return [
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
    ]

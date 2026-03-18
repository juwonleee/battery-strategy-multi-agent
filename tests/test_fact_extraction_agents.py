import pytest
from pydantic import ValidationError

from agents.catl_analysis import catl_analysis_agent
from agents.lges_analysis import lges_analysis_agent
from agents.market_research import market_research_agent
from state import (
    AtomicFactClaim,
    CATLFactExtractionOutput,
    EvidenceRef,
    LGESFactExtractionOutput,
    MarketFactExtractionOutput,
    MetricFactClaim,
)
from tools.openai_client import StructuredOutputError


class _FakeRetriever:
    def __init__(self, evidence_refs):
        self._evidence_refs = evidence_refs

    def retrieve(self, _query, *, scope, top_k):
        return list(self._evidence_refs[:top_k])


def test_market_research_agent_emits_fact_packet_and_compatibility_context(
    monkeypatch,
    sample_state,
):
    market_ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)

    monkeypatch.setattr(
        "agents.market_research._load_retriever",
        lambda _config: _FakeRetriever([market_ref]),
    )
    monkeypatch.setattr(
        "agents.market_research.invoke_structured_output",
        lambda **_kwargs: {
            "scope": "market",
            "summary": "정책과 수요 변동이 비교의 핵심 외생 변수다.",
            "atomic_claims": [
                {
                    "scope": "market",
                    "category": "market_overview",
                    "ordinal": 1,
                    "claim_text": "배터리 공급망은 지역화 압력을 받고 있다.",
                    "evidence_refs": [market_ref.model_dump(mode="json")],
                },
                {
                    "scope": "market",
                    "category": "comparison_axis",
                    "ordinal": 2,
                    "claim_text": "지역 생산 대응력",
                    "evidence_refs": [market_ref.model_dump(mode="json")],
                },
            ],
            "metric_claims": [],
            "source_evidence_refs": [market_ref.model_dump(mode="json")],
        },
    )

    result = market_research_agent(sample_state)

    assert result["status"] == "running"
    assert result["market_facts"].scope == "market"
    assert result["market_context"].summary == "정책과 수요 변동이 비교의 핵심 외생 변수다."
    assert result["market_context"].comparison_axes == ["지역 생산 대응력"]


def test_lges_analysis_agent_recovers_when_required_metric_family_missing(
    monkeypatch,
    sample_state,
):
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)

    monkeypatch.setattr(
        "agents.lges_analysis._load_retriever",
        lambda _config: _FakeRetriever([lges_ref]),
    )
    monkeypatch.setattr(
        "agents.lges_analysis.invoke_structured_output",
        lambda **_kwargs: {
            "scope": "lges",
            "summary": "LGES는 북미 현지화와 ESS 확대를 추진한다.",
            "atomic_claims": [
                {
                    "scope": "lges",
                    "category": "business_overview",
                    "ordinal": 1,
                    "claim_text": "LGES는 EV와 ESS를 병행 확대하고 있다.",
                    "evidence_refs": [lges_ref.model_dump(mode="json")],
                }
            ],
            "metric_claims": [
                _metric_claim_payload(
                    scope="lges",
                    category="revenue_growth_guidance",
                    ordinal=1,
                    metric_name="Revenue growth guidance",
                    value="mid-teen",
                    evidence_ref=lges_ref,
                ),
                _metric_claim_payload(
                    scope="lges",
                    category="operating_margin_guidance_or_actual",
                    ordinal=2,
                    metric_name="Operating margin",
                    value="mid-single digit",
                    evidence_ref=lges_ref,
                ),
                _metric_claim_payload(
                    scope="lges",
                    category="capex",
                    ordinal=3,
                    metric_name="Capex",
                    value="KRW 10tn",
                    evidence_ref=lges_ref,
                ),
                _metric_claim_payload(
                    scope="lges",
                    category="ess_capacity",
                    ordinal=4,
                    metric_name="ESS capacity",
                    value="15GWh",
                    evidence_ref=lges_ref,
                ),
            ],
            "source_evidence_refs": [lges_ref.model_dump(mode="json")],
        },
    )

    result = lges_analysis_agent(sample_state)

    assert result["status"] == "running"
    assert "secured_order_volume" in result["lges_facts"].metric_families()


def test_catl_analysis_agent_recovers_when_required_raw_metric_family_missing(
    monkeypatch,
    sample_state,
):
    catl_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p005-c01", page=5)

    monkeypatch.setattr(
        "agents.catl_analysis._load_retriever",
        lambda _config: _FakeRetriever([catl_ref]),
    )
    monkeypatch.setattr(
        "agents.catl_analysis.invoke_structured_output",
        lambda **_kwargs: {
            "scope": "catl",
            "summary": "CATL은 EV와 ESS에서 규모 우위를 확장한다.",
            "atomic_claims": [
                {
                    "scope": "catl",
                    "category": "business_overview",
                    "ordinal": 1,
                    "claim_text": "CATL은 EV와 ESS 양축으로 사업을 확장한다.",
                    "evidence_refs": [catl_ref.model_dump(mode="json")],
                }
            ],
            "metric_claims": [
                _metric_claim_payload(
                    scope="catl",
                    category="revenue",
                    ordinal=1,
                    metric_name="Revenue",
                    value="CNY 400bn",
                    evidence_ref=catl_ref,
                ),
                _metric_claim_payload(
                    scope="catl",
                    category="gross_profit_margin",
                    ordinal=2,
                    metric_name="Gross profit margin",
                    value="23%",
                    evidence_ref=catl_ref,
                ),
                _metric_claim_payload(
                    scope="catl",
                    category="net_profit_margin",
                    ordinal=3,
                    metric_name="Net profit margin",
                    value="11%",
                    evidence_ref=catl_ref,
                ),
                _metric_claim_payload(
                    scope="catl",
                    category="roe",
                    ordinal=4,
                    metric_name="ROE",
                    value="19%",
                    evidence_ref=catl_ref,
                ),
                _metric_claim_payload(
                    scope="catl",
                    category="operating_cash_flow",
                    ordinal=5,
                    metric_name="Operating cash flow",
                    value="CNY 80bn",
                    evidence_ref=catl_ref,
                ),
            ],
            "source_evidence_refs": [catl_ref.model_dump(mode="json")],
        },
    )

    result = catl_analysis_agent(sample_state)

    assert result["status"] == "running"
    assert "profit_for_the_year" in result["catl_facts"].metric_families()


@pytest.mark.parametrize(
    ("claim_type", "payload"),
    [
        (
            AtomicFactClaim,
            {
                "scope": "lges",
                "category": "business_overview",
                "ordinal": 1,
                "claim_text": "LGES는 북미 생산 확대를 추진한다.",
                "evidence_refs": [],
            },
        ),
        (
            MetricFactClaim,
            {
                "scope": "lges",
                "category": "capex",
                "ordinal": 2,
                "claim_text": "LGES는 대규모 CAPEX를 유지한다.",
                "metric_name": "Capex",
                "value": "KRW 10tn",
                "evidence_refs": [],
            },
        ),
    ],
)
def test_atomic_and_metric_claims_require_non_empty_evidence_refs(claim_type, payload):
    with pytest.raises(ValidationError):
        claim_type(**payload)


def test_atomic_and_metric_claims_accept_evidence_refs():
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)

    atomic_claim = AtomicFactClaim(
        scope="lges",
        category="business_overview",
        ordinal=1,
        claim_text="LGES는 북미 생산 확대를 추진한다.",
        evidence_refs=[lges_ref],
    )
    metric_claim = MetricFactClaim(
        scope="lges",
        category="capex",
        ordinal=2,
        claim_text="LGES는 대규모 CAPEX를 유지한다.",
        metric_name="Capex",
        value="KRW 10tn",
        evidence_refs=[lges_ref],
    )

    assert atomic_claim.evidence_refs[0].document_id == "lges-001"
    assert metric_claim.evidence_refs[0].document_id == "lges-001"


def test_market_research_agent_surfaces_hard_gate_failure(monkeypatch, sample_state):
    market_ref = EvidenceRef(document_id="market-001", chunk_id="market-001-p001-c01", page=1)
    invalid_claim = AtomicFactClaim.model_construct(
        scope="market",
        category="market_overview",
        ordinal=1,
        claim_id="market-market_overview-1",
        claim_text="근거 누락 주장",
        evidence_refs=[],
    )
    invalid_output = MarketFactExtractionOutput.model_construct(
        scope="market",
        summary="시장 요약",
        atomic_claims=[invalid_claim],
        metric_claims=[],
        source_evidence_refs=[market_ref],
    )

    monkeypatch.setattr(
        "agents.market_research._load_retriever",
        lambda _config: _FakeRetriever([market_ref]),
    )
    monkeypatch.setattr(
        "agents.market_research.invoke_structured_output",
        lambda **_kwargs: invalid_output,
    )

    result = market_research_agent(sample_state)

    assert result["status"] == "failed"
    assert result["last_error"].startswith("[hard-gate:fact-claim-evidence]")


def test_lges_analysis_agent_surfaces_hard_gate_failure(monkeypatch, sample_state):
    lges_ref = EvidenceRef(document_id="lges-001", chunk_id="lges-001-p003-c01", page=3)
    invalid_metric = MetricFactClaim.model_construct(
        scope="lges",
        category="capex",
        ordinal=1,
        claim_id="lges-capex-1",
        claim_text="CAPEX 근거 누락",
        metric_name="Capex",
        value="KRW 10tn",
        evidence_refs=[],
    )
    invalid_output = LGESFactExtractionOutput.model_construct(
        scope="lges",
        summary="LGES 요약",
        atomic_claims=[],
        metric_claims=[
            MetricFactClaim(
                scope="lges",
                category="revenue_growth_guidance",
                ordinal=2,
                claim_text="Revenue growth guidance: mid-teen",
                metric_name="Revenue growth guidance",
                value="mid-teen",
                evidence_refs=[lges_ref],
            ),
            MetricFactClaim(
                scope="lges",
                category="operating_margin_guidance_or_actual",
                ordinal=3,
                claim_text="Operating margin: 7.2%",
                metric_name="Operating margin",
                value="7.2%",
                evidence_refs=[lges_ref],
            ),
            invalid_metric,
            MetricFactClaim(
                scope="lges",
                category="ess_capacity",
                ordinal=4,
                claim_text="ESS capacity: 15GWh",
                metric_name="ESS capacity",
                value="15GWh",
                evidence_refs=[lges_ref],
            ),
            MetricFactClaim(
                scope="lges",
                category="secured_order_volume",
                ordinal=5,
                claim_text="Secured order volume: 100GWh",
                metric_name="Secured order volume",
                value="100GWh",
                evidence_refs=[lges_ref],
            ),
        ],
        source_evidence_refs=[lges_ref],
    )

    monkeypatch.setattr(
        "agents.lges_analysis._load_retriever",
        lambda _config: _FakeRetriever([lges_ref]),
    )
    monkeypatch.setattr(
        "agents.lges_analysis.invoke_structured_output",
        lambda **_kwargs: invalid_output,
    )

    result = lges_analysis_agent(sample_state)

    assert result["status"] == "failed"
    assert result["last_error"].startswith("[hard-gate:fact-claim-evidence]")


def test_catl_analysis_agent_surfaces_hard_gate_failure(monkeypatch, sample_state):
    catl_ref = EvidenceRef(document_id="catl-001", chunk_id="catl-001-p008-c01", page=8)
    invalid_metric = MetricFactClaim.model_construct(
        scope="catl",
        category="profit_for_the_year",
        ordinal=2,
        claim_id="catl-profit_for_the_year-2",
        claim_text="Profit for the year: CNY 44bn",
        metric_name="Profit for the year",
        value="CNY 44bn",
        evidence_refs=[],
    )
    invalid_output = CATLFactExtractionOutput.model_construct(
        scope="catl",
        summary="CATL 요약",
        atomic_claims=[],
        metric_claims=[
            MetricFactClaim(
                scope="catl",
                category="revenue",
                ordinal=1,
                claim_text="Revenue: CNY 400bn",
                metric_name="Revenue",
                value="CNY 400bn",
                evidence_refs=[catl_ref],
            ),
            invalid_metric,
            MetricFactClaim(
                scope="catl",
                category="gross_profit_margin",
                ordinal=3,
                claim_text="Gross profit margin: 23%",
                metric_name="Gross profit margin",
                value="23%",
                evidence_refs=[catl_ref],
            ),
            MetricFactClaim(
                scope="catl",
                category="net_profit_margin",
                ordinal=4,
                claim_text="Net profit margin: 11%",
                metric_name="Net profit margin",
                value="11%",
                evidence_refs=[catl_ref],
            ),
            MetricFactClaim(
                scope="catl",
                category="roe",
                ordinal=5,
                claim_text="ROE: 19%",
                metric_name="ROE",
                value="19%",
                evidence_refs=[catl_ref],
            ),
            MetricFactClaim(
                scope="catl",
                category="operating_cash_flow",
                ordinal=6,
                claim_text="Operating cash flow: CNY 80bn",
                metric_name="Operating cash flow",
                value="CNY 80bn",
                evidence_refs=[catl_ref],
            ),
        ],
        source_evidence_refs=[catl_ref],
    )

    monkeypatch.setattr(
        "agents.catl_analysis._load_retriever",
        lambda _config: _FakeRetriever([catl_ref]),
    )
    monkeypatch.setattr(
        "agents.catl_analysis.invoke_structured_output",
        lambda **_kwargs: invalid_output,
    )

    result = catl_analysis_agent(sample_state)

    assert result["status"] == "failed"
    assert result["last_error"].startswith("[hard-gate:fact-claim-evidence]")


def test_lges_analysis_agent_uses_fallback_when_structured_output_fails(
    monkeypatch,
    sample_state,
):
    evidence_refs = [
        EvidenceRef(
            document_id="lges-25q4-performance",
            chunk_id="lges-25q4-performance-p001-c01",
            page=1,
            snippet=(
                "•【 46 Series 】 Start of production in Ochang, customer expansion toward "
                "traditional OEMs and Chinese OEMs, achieving 300GWh+ of order backlog "
                "•【 ESS 】 Securing order backlog of 140GWh"
            ),
        ),
        EvidenceRef(
            document_id="lges-25q4-performance",
            chunk_id="lges-25q4-performance-p007-c01",
            page=7,
            snippet=(
                "GlobalESS Capacity 2025-end 12GWh 2026-end 36GWh +More than 60GWh "
                "NorthAmerica ... Japan and Australia ... LFP and HV Mid-Ni ... 46 Series"
            ),
        ),
        EvidenceRef(
            document_id="lges-25q4-performance",
            chunk_id="lges-25q4-performance-p008-c01",
            page=8,
            snippet=(
                "Target to grow between +Mid-teen ~ +20% YoY of Revenue "
                "Target for +Mid-single% of OP Margin "
                "Target to reduce Capex by more than -40% YoY "
                "slowing EV demand in NA"
            ),
        ),
    ]

    monkeypatch.setattr(
        "agents.lges_analysis._load_retriever",
        lambda _config: _FakeRetriever(evidence_refs),
    )
    monkeypatch.setattr(
        "agents.lges_analysis.invoke_structured_output",
        lambda **_kwargs: (_ for _ in ()).throw(
            StructuredOutputError("forced LGES structured output failure")
        ),
    )

    result = lges_analysis_agent(sample_state)

    assert result["status"] == "running"
    assert result["lges_facts"].metric_families() == {
        "revenue_growth_guidance",
        "operating_margin_guidance_or_actual",
        "capex",
        "ess_capacity",
        "secured_order_volume",
    }


def test_catl_analysis_agent_uses_fallback_when_structured_output_fails(
    monkeypatch,
    sample_state,
):
    evidence_refs = [
        EvidenceRef(
            document_id="catl-prospectus",
            chunk_id="catl-prospectus-p004-c02",
            page=4,
            snippet=(
                "our revenue was RMB328.6 billion, RMB400.9 billion and RMB362.0 billion "
                "profit for the year was RMB33.5 billion, RMB47.3 billion and RMB55.3 billion "
                "net profit margin for the years ended December 31, 2022, 2023 and 2024 "
                "was 10.2%, 11.8% and 15.3%, respectively. "
                "weighted average ROE was 24.7%, 24.3% and 24.7%, respectively. "
                "net cash flow generated from operating activities ... RMB97.0 billion."
            ),
        ),
        EvidenceRef(
            document_id="catl-prospectus",
            chunk_id="catl-prospectus-p011-c01",
            page=11,
            snippet=(
                "Net cash generated from operating activities 61,208,844 92,826,125 96,990,344 "
                "Net profit margin 10.2% 11.8% 15.3% "
                "Weighted average return on equity (ROE) 24.7% 24.3% 24.7%"
            ),
        ),
        EvidenceRef(
            document_id="catl-prospectus",
            chunk_id="catl-prospectus-p046-c02",
            page=46,
            snippet=(
                "globally leading innovative new energy technology company "
                "EV batteries and ESS batteries "
                "integrated innovative solutions"
            ),
        ),
        EvidenceRef(
            document_id="catl-prospectus",
            chunk_id="catl-prospectus-p047-c01",
            page=47,
            snippet="Germany Hungary Spain Indonesia",
        ),
        EvidenceRef(
            document_id="catl-prospectus",
            chunk_id="catl-prospectus-p045-c02",
            page=45,
            snippet="additional tariffs average selling price raw materials",
        ),
        EvidenceRef(
            document_id="catl-prospectus",
            chunk_id="catl-prospectus-p007-c01",
            page=7,
            snippet="Revenue 328,593,988 400,917,045 362,012,554 Gross profit 57,964,208 76,934,915 88,493,595",
        ),
    ]

    monkeypatch.setattr(
        "agents.catl_analysis._load_retriever",
        lambda _config: _FakeRetriever(evidence_refs),
    )
    monkeypatch.setattr(
        "agents.catl_analysis.invoke_structured_output",
        lambda **_kwargs: (_ for _ in ()).throw(
            StructuredOutputError("forced CATL structured output failure")
        ),
    )

    result = catl_analysis_agent(sample_state)

    assert result["status"] == "running"
    assert result["catl_facts"].metric_families() == {
        "revenue",
        "profit_for_the_year",
        "gross_profit_margin",
        "net_profit_margin",
        "roe",
        "operating_cash_flow",
    }


def _metric_claim_payload(
    *,
    scope: str,
    category: str,
    ordinal: int,
    metric_name: str,
    value: str,
    evidence_ref: EvidenceRef,
):
    return {
        "scope": scope,
        "category": category,
        "ordinal": ordinal,
        "claim_text": f"{metric_name}: {value}",
        "metric_name": metric_name,
        "value": value,
        "evidence_refs": [evidence_ref.model_dump(mode="json")],
    }

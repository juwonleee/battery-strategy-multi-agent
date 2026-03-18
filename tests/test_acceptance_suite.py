import json
from copy import deepcopy
from pathlib import Path

import app
import graph
from state import ReportSpec, build_initial_state
from tools.reporting import assemble_html_report, assemble_markdown_report


def test_minimal_report_spec_fixture_matches_submission_shape(sample_state):
    fixture_path = Path(__file__).parent / "fixtures" / "minimal_report_spec.json"
    report_spec = ReportSpec.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    state = {
        **deepcopy(sample_state),
        "goal": "LGES와 CATL의 다각화 전략을 비교 분석한다",
        "report_spec": report_spec,
    }

    markdown = assemble_markdown_report(state)
    html = assemble_html_report(state)

    assert "## Summary" in markdown
    assert "## 정량 비교표" in markdown
    assert "## 차트" in markdown
    assert "## 종합 판단" in markdown
    assert "CATL은 포트폴리오 선택지가 더 넓고" in markdown
    assert "Revenue Trend" in html
    assert "Reported Profitability" in html
    assert "Sample Market Report" in html


def test_full_workflow_e2e_runs_through_graph_and_exports_reports(
    monkeypatch,
    sample_state,
    sample_documents,
    preprocessing_summary,
    test_config,
):
    synthetic_outputs = deepcopy(sample_state)
    state = build_initial_state(
        test_config,
        source_documents=sample_documents,
        retrieval_handles={"faiss_index_path": str(test_config.faiss_index_path)},
        preprocessing_summary=preprocessing_summary,
    )

    def fake_market_agent(current_state):
        return {
            "market_context": synthetic_outputs["market_context"],
            "market_context_summary": synthetic_outputs["market_context_summary"],
            "citation_refs": synthetic_outputs["citation_refs"][:1],
            "status": "running",
            "last_error": None,
        }

    def fake_lges_agent(current_state):
        return {
            "lges_profile": synthetic_outputs["lges_profile"],
            "citation_refs": synthetic_outputs["citation_refs"][:2],
            "status": "running",
            "last_error": None,
        }

    def fake_catl_agent(current_state):
        return {
            "catl_profile": synthetic_outputs["catl_profile"],
            "citation_refs": synthetic_outputs["citation_refs"][:3],
            "status": "running",
            "last_error": None,
        }

    def fake_comparison_agent(current_state):
        return {
            "comparison_input_spec": synthetic_outputs.get("comparison_input_spec"),
            "synthesis_claims": synthetic_outputs["synthesis_claims"],
            "score_criteria": synthetic_outputs["score_criteria"],
            "final_judgment": synthetic_outputs["final_judgment"],
            "metric_comparison_rows": synthetic_outputs["metric_comparison_rows"],
            "charts": synthetic_outputs["charts"],
            "comparison_matrix": synthetic_outputs["comparison_matrix"],
            "swot_matrix": synthetic_outputs["swot_matrix"],
            "scorecard": synthetic_outputs["scorecard"],
            "low_confidence_claims": synthetic_outputs["low_confidence_claims"],
            "status": "running",
            "last_error": None,
        }

    def fake_review_agent(current_state):
        return {
            "review_result": synthetic_outputs["review_result"],
            "review_issues": synthetic_outputs["review_issues"],
            "validation_warnings": synthetic_outputs["validation_warnings"],
            "status": "reviewed",
            "last_error": None,
        }

    monkeypatch.setitem(graph.AGENT_REGISTRY, "market_research", fake_market_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "lges_analysis", fake_lges_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "catl_analysis", fake_catl_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "comparison", fake_comparison_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "review", fake_review_agent)
    monkeypatch.setattr(
        app,
        "export_pdf_report",
        lambda _html, output_path: output_path.write_bytes(b"%PDF-1.4\n%acceptance\n"),
    )

    for _ in range(10):
        state = graph.run_once(state)
        if state.get("current_step") == "finish":
            break

    assert state["status"] == "completed"
    assert state["review_result"].passed is True
    assert state["comparison_matrix"]
    assert state["charts"]

    exported_state = app._export_reports(state)

    assert exported_state["status"] == "completed"
    assert test_config.output_markdown_path.exists()
    assert test_config.output_html_path.exists()
    assert test_config.output_pdf_path.exists()

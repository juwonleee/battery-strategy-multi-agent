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

    assert "## Executive Summary" in markdown
    assert "## 비교 프레임과 방법" in markdown
    assert "## 직접 비교표" in markdown
    assert "## 참고 지표표" in markdown
    assert "## 차트와 해석" in markdown
    assert "## SWOT" in markdown
    assert "## Scorecard" in markdown
    assert "## 종합 판단" in markdown
    assert "Quick Comparison" in markdown
    assert "Revenue Comparison" in html
    assert "Sample Market Report" in html
    assert "Reference" in html


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

    def fake_blueprint_agent(current_state):
        return {
            "report_blueprint": synthetic_outputs["report_blueprint"],
            "status": "running",
            "last_error": None,
        }

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
            "metric_comparison_rows": synthetic_outputs["metric_comparison_rows"],
            "comparison_matrix": synthetic_outputs["comparison_matrix"],
            "low_confidence_claims": synthetic_outputs["low_confidence_claims"],
            "status": "running",
            "last_error": None,
        }

    def fake_supervisor_synthesis_agent(current_state):
        return {
            "selected_comparison_rows": synthetic_outputs["selected_comparison_rows"],
            "reference_only_rows": synthetic_outputs["reference_only_rows"],
            "chart_selection": synthetic_outputs["chart_selection"],
            "executive_summary": synthetic_outputs["executive_summary"],
            "company_strategy_summaries": synthetic_outputs["company_strategy_summaries"],
            "quick_comparison_panel": synthetic_outputs["quick_comparison_panel"],
            "supervisor_swot": synthetic_outputs["supervisor_swot"],
            "supervisor_score_rationales": synthetic_outputs["supervisor_score_rationales"],
            "final_judgment": synthetic_outputs["final_judgment"],
            "implications": synthetic_outputs["implications"],
            "limitations": synthetic_outputs["limitations"],
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

    monkeypatch.setitem(graph.AGENT_REGISTRY, "supervisor_blueprint", fake_blueprint_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "market_research", fake_market_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "lges_analysis", fake_lges_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "catl_analysis", fake_catl_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "comparison", fake_comparison_agent)
    monkeypatch.setitem(graph.AGENT_REGISTRY, "supervisor_synthesis", fake_supervisor_synthesis_agent)
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
    assert state["selected_comparison_rows"]
    assert state["chart_selection"]

    exported_state = app._export_reports(state)

    assert exported_state["status"] == "completed"
    assert test_config.output_markdown_path.exists()
    assert test_config.output_html_path.exists()
    assert test_config.output_pdf_path.exists()

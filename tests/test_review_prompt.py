import json

from prompts import build_review_prompt
from tools.reporting import build_report_spec


def test_build_review_prompt_includes_report_spec_and_validation_warnings(sample_state):
    report_spec = build_report_spec(sample_state)

    prompt = build_review_prompt(
        market_context_summary=sample_state["market_context_summary"],
        comparison_matrix=sample_state["comparison_matrix"],
        swot_matrix=sample_state["swot_matrix"],
        scorecard=sample_state["scorecard"],
        low_confidence_claims=sample_state["low_confidence_claims"],
        report_spec=report_spec,
        validation_warnings=["Summary text exactly duplicates the final judgment."],
    )
    payload = json.loads(prompt.input_text)

    assert "report_spec" in payload
    assert payload["report_spec"]["title"] == "배터리 전략 비교 보고서"
    assert payload["report_spec"]["final_judgment"]["judgment_text"]
    assert payload["validation_warnings"] == [
        "Summary text exactly duplicates the final judgment."
    ]
    assert "report_spec 전체를 함께 검토한다" in prompt.instructions
    assert "primary input" in prompt.instructions

from pathlib import Path

from tools.reporting import assemble_markdown_report, export_markdown_report


def test_assemble_markdown_report_includes_key_sections(sample_state):
    markdown = assemble_markdown_report(sample_state)

    assert "# 배터리 전략 비교 보고서" in markdown
    assert "## 시장 배경" in markdown
    assert "## 비교표" in markdown
    assert "## 참고문헌" in markdown
    assert "LG Energy Solution" in markdown
    assert "CATL" in markdown


def test_export_markdown_report_writes_file(sample_state, tmp_path: Path):
    markdown = assemble_markdown_report(sample_state)
    output_path = tmp_path / "report.md"

    export_markdown_report(markdown, output_path)

    assert output_path.exists()
    assert "배터리 전략 비교 보고서" in output_path.read_text(encoding="utf-8")

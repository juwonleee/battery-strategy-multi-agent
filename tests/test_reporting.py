from pathlib import Path

from tools.reporting import assemble_markdown_report, export_markdown_report


def test_assemble_markdown_report_includes_key_sections(sample_state):
    markdown = assemble_markdown_report(sample_state)

    assert "# Battery Strategy Comparison Report" in markdown
    assert "## Market Background" in markdown
    assert "## Comparison Matrix" in markdown
    assert "## References" in markdown
    assert "LG Energy Solution" in markdown
    assert "CATL" in markdown


def test_export_markdown_report_writes_file(sample_state, tmp_path: Path):
    markdown = assemble_markdown_report(sample_state)
    output_path = tmp_path / "report.md"

    export_markdown_report(markdown, output_path)

    assert output_path.exists()
    assert "Battery Strategy Comparison Report" in output_path.read_text(encoding="utf-8")

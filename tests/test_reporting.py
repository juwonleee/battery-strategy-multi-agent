from pathlib import Path
import re

import pytest

from state import AtomicFactClaim, MarketFactExtractionOutput
from tools.reporting import (
    assemble_html_report,
    assemble_markdown_report,
    build_report_spec,
    export_html_report,
    export_markdown_report,
    export_pdf_report,
)


def test_assemble_markdown_report_includes_required_sections_in_order(sample_state):
    markdown = assemble_markdown_report(sample_state)

    assert "# 배터리 전략 비교 보고서" in markdown
    assert "LG Energy Solution" in markdown
    assert "CATL" in markdown
    section_order = [
        "## Executive Summary",
        "## 비교 프레임과 방법",
        "## 시장 배경",
        "## LGES 전략 요약",
        "## CATL 전략 요약",
        "## Quick Comparison",
        "## 직접 비교표",
        "## 참고 지표표",
        "## 차트와 해석",
        "## SWOT",
        "## Scorecard",
        "## 종합 판단",
        "## 시사점",
        "## 한계와 주의사항",
        "## Reference",
    ]
    positions = [markdown.index(section) for section in section_order]
    assert positions == sorted(positions)
    assert "## 차트" in markdown


def test_assemble_markdown_report_renders_inline_citations(sample_state):
    markdown = assemble_markdown_report(sample_state)

    assert (
        "[Sample Market Report p.1]" in markdown
        or "[Sample LGES Deck p.3]" in markdown
        or "[Sample CATL Prospectus p.5]" in markdown
    )


def test_export_markdown_report_writes_file(sample_state, tmp_path: Path):
    markdown = assemble_markdown_report(sample_state)
    output_path = tmp_path / "report.md"

    export_markdown_report(markdown, output_path)

    assert output_path.exists()
    assert "배터리 전략 비교 보고서" in output_path.read_text(encoding="utf-8")


def test_assemble_html_report_includes_structured_sections(sample_state):
    html = assemble_html_report(sample_state)

    assert "<html" in html
    assert "summary-grid" in html
    assert "comparison-table" in html
    assert "chart-grid" in html
    assert "swot-grid" in html
    assert "scorecard-grid" in html
    assert "LG Energy Solution" in html
    assert "Sample LGES Deck" in html
    assert "Sample CATL Prospectus" in html
    assert ">차트와 해석<" in html


def test_assemble_html_report_uses_pdf_document_template(sample_state):
    html = assemble_html_report(sample_state)

    assert "@page {" in html
    assert "@media print" in html
    assert "linear-gradient" not in html
    assert "box-shadow" not in html
    assert "page-break-before: always" not in html
    assert "break-before: page" not in html
    assert "border-left: 4px solid var(--accent);" in html


def test_assemble_html_report_keeps_non_cover_content_dense(sample_state):
    html = assemble_html_report(sample_state)
    section_html = "".join(re.findall(r"<section class=\"section\">(.*?)</section>", html, re.DOTALL))
    text_only = re.sub(r"<[^>]+>", " ", section_html)
    non_whitespace_characters = len(re.sub(r"\s+", "", text_only))

    assert non_whitespace_characters >= 150


def test_assemble_html_report_does_not_introduce_forced_blank_page_rules(sample_state):
    html = assemble_html_report(sample_state)

    assert "page-break-before: always" not in html
    assert "break-before: page" not in html
    assert "page-break-inside: avoid" in html


def test_assemble_report_requires_final_judgment(sample_state):
    state = dict(sample_state)
    state["final_judgment"] = None

    with pytest.raises(ValueError, match="Final judgment is required"):
        assemble_markdown_report(state)


def test_build_report_spec_dedupes_duplicate_claim_ids(sample_state):
    state = dict(sample_state)
    market_ref = state["market_context"].evidence_refs[0]
    market_claim = AtomicFactClaim(
        scope="market",
        category="market_overview",
        ordinal=1,
        claim_text="시장 수요가 지역화되고 있다.",
        evidence_refs=[market_ref],
    )
    state["market_facts"] = MarketFactExtractionOutput(
        scope="market",
        summary="시장 요약",
        atomic_claims=[market_claim, market_claim],
        metric_claims=[],
        source_evidence_refs=[market_ref],
    )

    report_spec = build_report_spec(state)

    claim_ids = [claim.claim_id for claim in report_spec.atomic_claims]
    assert len(claim_ids) == len(set(claim_ids))


def test_export_html_report_writes_file(sample_state, tmp_path: Path):
    html = assemble_html_report(sample_state)
    output_path = tmp_path / "report.html"

    export_html_report(html, output_path)

    assert output_path.exists()
    assert "배터리 전략 비교 보고서" in output_path.read_text(encoding="utf-8")


def test_export_pdf_report_uses_print_media_and_writes_file(monkeypatch, sample_state, tmp_path: Path):
    html = assemble_html_report(sample_state)
    output_path = tmp_path / "report.pdf"
    calls = {}

    class _FakePage:
        def set_content(self, content, wait_until):
            calls["content"] = content
            calls["wait_until"] = wait_until

        def emulate_media(self, media):
            calls["media"] = media

        def pdf(self, **kwargs):
            calls["pdf_kwargs"] = kwargs
            Path(kwargs["path"]).write_bytes(b"%PDF-1.4\n%fake\n")

    class _FakeBrowser:
        def new_page(self):
            return _FakePage()

        def close(self):
            calls["closed"] = True

    class _FakePlaywrightContext:
        def __enter__(self):
            class _Playwright:
                chromium = type("_Chromium", (), {"launch": staticmethod(lambda: _FakeBrowser())})()

            return _Playwright()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("tools.reporting.sync_playwright", lambda: _FakePlaywrightContext())

    export_pdf_report(html, output_path)

    assert output_path.exists()
    assert calls["wait_until"] == "networkidle"
    assert calls["media"] == "print"
    assert calls["pdf_kwargs"]["print_background"] is False

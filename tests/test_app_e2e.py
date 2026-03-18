from copy import deepcopy

import app
from tools.reporting import ReportExportError


def test_main_exports_reports_and_log(
    monkeypatch,
    capsys,
    sample_state,
    sample_documents,
    preprocessing_summary,
    test_config,
):
    completed_state = deepcopy(sample_state)

    def fake_load_config(_root_dir):
        return test_config

    def fake_prepare_document_corpus(_config):
        return sample_documents, {"processed_corpus_path": str(test_config.processed_corpus_path)}, preprocessing_summary

    def fake_prepare_retrieval_assets(_config):
        return {"faiss_index_path": str(test_config.faiss_index_path)}

    def fake_run_once(_state):
        return completed_state

    def fake_export_pdf_report(_html, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-1.4\n%test\n")

    monkeypatch.setattr(app, "load_config", fake_load_config)
    monkeypatch.setattr(app, "prepare_document_corpus", fake_prepare_document_corpus)
    monkeypatch.setattr(app, "prepare_retrieval_assets", fake_prepare_retrieval_assets)
    monkeypatch.setattr(app, "run_once", fake_run_once)
    monkeypatch.setattr(app, "export_pdf_report", fake_export_pdf_report)

    app.main()
    output = capsys.readouterr().out

    assert "Workflow finished: completed" in output
    assert test_config.output_markdown_path.exists()
    assert test_config.output_html_path.exists()
    assert test_config.output_pdf_path.exists()
    assert test_config.log_path.exists()
    log_text = test_config.log_path.read_text(encoding="utf-8")
    assert "Markdown report exported" in log_text
    assert "HTML report exported" in log_text
    assert "PDF report exported" in log_text


def test_main_skips_pdf_when_playwright_export_fails(
    monkeypatch,
    capsys,
    sample_state,
    sample_documents,
    preprocessing_summary,
    test_config,
):
    completed_state = deepcopy(sample_state)

    def fake_load_config(_root_dir):
        return test_config

    def fake_prepare_document_corpus(_config):
        return sample_documents, {"processed_corpus_path": str(test_config.processed_corpus_path)}, preprocessing_summary

    def fake_prepare_retrieval_assets(_config):
        return {"faiss_index_path": str(test_config.faiss_index_path)}

    def fake_run_once(_state):
        return completed_state

    def fake_export_pdf_report(_html, _output_path):
        raise ReportExportError("chromium missing")

    monkeypatch.setattr(app, "load_config", fake_load_config)
    monkeypatch.setattr(app, "prepare_document_corpus", fake_prepare_document_corpus)
    monkeypatch.setattr(app, "prepare_retrieval_assets", fake_prepare_retrieval_assets)
    monkeypatch.setattr(app, "run_once", fake_run_once)
    monkeypatch.setattr(app, "export_pdf_report", fake_export_pdf_report)

    app.main()
    output = capsys.readouterr().out

    assert "Workflow finished: completed" in output
    assert test_config.output_markdown_path.exists()
    assert test_config.output_html_path.exists()
    assert not test_config.output_pdf_path.exists()
    log_text = test_config.log_path.read_text(encoding="utf-8")
    assert "HTML report exported" in log_text
    assert "PDF export skipped: chromium missing" in log_text


def test_main_blocks_partial_export_when_final_validation_fails(
    monkeypatch,
    capsys,
    sample_state,
    sample_documents,
    preprocessing_summary,
    test_config,
):
    completed_state = deepcopy(sample_state)
    completed_state["final_judgment"] = None

    def fake_load_config(_root_dir):
        return test_config

    def fake_prepare_document_corpus(_config):
        return sample_documents, {"processed_corpus_path": str(test_config.processed_corpus_path)}, preprocessing_summary

    def fake_prepare_retrieval_assets(_config):
        return {"faiss_index_path": str(test_config.faiss_index_path)}

    def fake_run_once(_state):
        return completed_state

    monkeypatch.setattr(app, "load_config", fake_load_config)
    monkeypatch.setattr(app, "prepare_document_corpus", fake_prepare_document_corpus)
    monkeypatch.setattr(app, "prepare_retrieval_assets", fake_prepare_retrieval_assets)
    monkeypatch.setattr(app, "run_once", fake_run_once)

    app.main()
    output = capsys.readouterr().out

    assert "Workflow finished: failed" in output
    assert not test_config.output_markdown_path.exists()
    assert not test_config.output_html_path.exists()
    assert not test_config.output_pdf_path.exists()
    log_text = test_config.log_path.read_text(encoding="utf-8")
    assert "Report export blocked by final validation" in log_text


def test_export_reports_preserves_soft_warnings(sample_state):
    state = deepcopy(sample_state)
    state["market_context"].summary = state["final_judgment"].judgment_text

    exported = app._export_reports(state)

    assert exported["status"] == "completed"
    assert any(
        "Summary text exactly duplicates" in warning
        for warning in exported["validation_warnings"]
    )

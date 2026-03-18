from copy import deepcopy

import app


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

    monkeypatch.setattr(app, "load_config", fake_load_config)
    monkeypatch.setattr(app, "prepare_document_corpus", fake_prepare_document_corpus)
    monkeypatch.setattr(app, "prepare_retrieval_assets", fake_prepare_retrieval_assets)
    monkeypatch.setattr(app, "run_once", fake_run_once)

    app.main()
    output = capsys.readouterr().out

    assert "Workflow finished: completed" in output
    assert test_config.output_markdown_path.exists()
    assert test_config.output_pdf_path.exists()
    assert test_config.log_path.exists()
    log_text = test_config.log_path.read_text(encoding="utf-8")
    assert "Markdown report exported" in log_text
    assert "PDF report exported" in log_text

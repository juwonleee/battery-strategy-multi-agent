from pathlib import Path

from config import load_config
from state import AgentState, ReportArtifact, append_execution_log, build_initial_state
from tools.preprocessing import prepare_document_corpus
from tools.reporting import (
    ReportExportError,
    assemble_html_report,
    assemble_markdown_report,
    export_html_report,
    export_markdown_report,
    export_pdf_report,
    mark_report_artifact_status,
)
from tools.validation import validate_final_delivery_state


MAX_WORKFLOW_ITERATIONS = 20


def run_once(state: AgentState) -> AgentState:
    from graph import run_once as _run_once

    return _run_once(state)


def write_execution_log(state: AgentState, log_path: Path) -> None:
    from graph import write_execution_log as _write_execution_log

    _write_execution_log(state, log_path)


def prepare_retrieval_assets(config):
    from tools.retrieval import prepare_retrieval_assets as _prepare_retrieval_assets

    return _prepare_retrieval_assets(config)


def main() -> None:
    config = load_config(Path(__file__).resolve().parent)
    documents, retrieval_handles, preprocessing_summary = prepare_document_corpus(
        config
    )
    retrieval_handles = {
        **retrieval_handles,
        **prepare_retrieval_assets(config),
    }

    state = build_initial_state(
        config,
        source_documents=documents,
        retrieval_handles=retrieval_handles,
        preprocessing_summary=preprocessing_summary,
    )

    for _ in range(MAX_WORKFLOW_ITERATIONS):
        if state.get("current_step") == "finish":
            break
        state = run_once(state)
        if state.get("current_step") == "finish":
            break
    else:
        state = _mark_iteration_limit_exceeded(state)

    if state.get("status") == "completed":
        state = _export_reports(state)

    write_execution_log(state, config.log_path)
    state["report_artifacts"] = _mark_artifact_created(
        state.get("report_artifacts", []),
        artifact_type="log",
        path=config.log_path,
        created=config.log_path.exists(),
    )

    print("Workflow finished:", state.get("status"))
    print("Output directory:", config.paths.outputs_dir)
    print("Processed corpus:", preprocessing_summary.processed_corpus_path)
    print("FAISS index:", retrieval_handles["faiss_index_path"])
    print("Execution log:", config.log_path)
    print("Markdown report:", config.output_markdown_path)
    print("HTML report:", config.output_html_path)
    print("PDF report:", config.output_pdf_path)


def _export_reports(state: AgentState) -> AgentState:
    config = state["config"]
    final_validation = validate_final_delivery_state(state)
    if final_validation.hard_errors:
        failed_state: AgentState = {
            **state,
            "status": "failed",
            "last_error": final_validation.hard_errors[0],
            "validation_warnings": final_validation.soft_warnings,
        }
        failed_state["execution_log"] = append_execution_log(
            failed_state,
            step="finish",
            status="failed",
            message=(
                "Report export blocked by final validation: "
                f"{final_validation.hard_errors[0]}"
            ),
        )
        return failed_state

    markdown = assemble_markdown_report(state)
    html = assemble_html_report(state)

    export_markdown_report(markdown, config.output_markdown_path)
    export_html_report(html, config.output_html_path)
    exported_state: AgentState = {
        **state,
        "report_artifacts": _mark_artifact_created(
            state.get("report_artifacts", []),
            artifact_type="markdown",
            path=config.output_markdown_path,
            created=True,
        ),
    }
    exported_state["report_artifacts"] = _mark_artifact_created(
        exported_state.get("report_artifacts", []),
        artifact_type="html",
        path=config.output_html_path,
        created=True,
    )
    exported_state["execution_log"] = append_execution_log(
        exported_state,
        step="finish",
        status="completed",
        message=f"Markdown report exported to {config.output_markdown_path}.",
    )
    exported_state["execution_log"] = append_execution_log(
        exported_state,
        step="finish",
        status="completed",
        message=f"HTML report exported to {config.output_html_path}.",
    )
    exported_state["validation_warnings"] = final_validation.soft_warnings

    try:
        export_pdf_report(html, config.output_pdf_path)
    except ReportExportError as exc:
        exported_state["report_artifacts"] = _mark_artifact_created(
            exported_state.get("report_artifacts", []),
            artifact_type="pdf",
            path=config.output_pdf_path,
            created=False,
        )
        exported_state["execution_log"] = append_execution_log(
            exported_state,
            step="finish",
            status="completed",
            message=f"PDF export skipped: {exc}",
        )
        return exported_state

    exported_state["report_artifacts"] = _mark_artifact_created(
        exported_state.get("report_artifacts", []),
        artifact_type="pdf",
        path=config.output_pdf_path,
        created=True,
    )
    exported_state["execution_log"] = append_execution_log(
        exported_state,
        step="finish",
        status="completed",
        message=f"PDF report exported to {config.output_pdf_path}.",
    )
    return exported_state


def _mark_iteration_limit_exceeded(state: AgentState) -> AgentState:
    limited_state = {
        **state,
        "current_step": "finish",
        "status": "failed",
        "routing_reason": f"Stopped after reaching iteration limit ({MAX_WORKFLOW_ITERATIONS}).",
        "last_error": "Workflow iteration limit exceeded.",
    }
    limited_state["execution_log"] = append_execution_log(
        limited_state,
        step="finish",
        status="failed",
        message="Workflow stopped after reaching the maximum iteration limit.",
        attempt=limited_state.get("review_retry_count", 0),
    )
    return limited_state


def _mark_artifact_created(
    artifacts: list[ReportArtifact],
    *,
    artifact_type: str,
    path: Path,
    created: bool,
) -> list[ReportArtifact]:
    return mark_report_artifact_status(
        artifacts,
        artifact_type=artifact_type,
        path=path,
        created=created,
    )


if __name__ == "__main__":
    main()

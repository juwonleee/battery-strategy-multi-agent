from pathlib import Path

from config import load_config
from graph import run_once, write_execution_log
from state import AgentState, ReportArtifact, append_execution_log, build_initial_state
from tools.preprocessing import prepare_document_corpus
from tools.reporting import (
    ReportExportError,
    assemble_markdown_report,
    export_markdown_report,
    export_pdf_report,
    mark_report_artifact_status,
)
from tools.retrieval import prepare_retrieval_assets


MAX_WORKFLOW_ITERATIONS = 20


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
    print("PDF report:", config.output_pdf_path)


def _export_reports(state: AgentState) -> AgentState:
    config = state["config"]
    markdown = assemble_markdown_report(state)

    export_markdown_report(markdown, config.output_markdown_path)
    exported_state = {
        **state,
        "report_artifacts": _mark_artifact_created(
            state.get("report_artifacts", []),
            artifact_type="markdown",
            path=config.output_markdown_path,
            created=True,
        ),
    }
    exported_state["execution_log"] = append_execution_log(
        exported_state,
        step="finish",
        status="completed",
        message=f"Markdown report exported to {config.output_markdown_path}.",
    )

    try:
        export_pdf_report(markdown, config.output_pdf_path)
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
